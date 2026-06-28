from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AssetStatus, Audio, Base, Job, JobStatus, JobType, Poem
from app.worker_tts import AudioWorker


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _seed(sf, lang="en"):
    with sf() as s:
        poem = Poem(
            character="sayori", title="t", poem_en="english text", poem_ja="日本語のテキスト"
        )
        audio = Audio(lang=lang)
        poem.audios.append(audio)
        s.add(poem)
        s.flush()
        job = Job(type=JobType.AUDIO, ref_id=audio.id)
        s.add(job)
        s.commit()
        return job.id, audio.id


class FakeRedis:
    """Minimal Redis double supporting the reliable-delivery list ops (#58)."""

    def __init__(self, queue=(), queue_name="jobs:audio"):
        self.lists: dict[str, list[bytes]] = {}
        if queue:
            self.lists[queue_name] = [str(i).encode() for i in queue]
        self.counters: dict[str, int] = {}
        self.expires: dict[str, int] = {}
        self.pushed: list[tuple[str, int]] = []

    def _list(self, key):
        return self.lists.setdefault(key, [])

    def _move(self, src, dst, srcpos, dstpos):
        s = self._list(src)
        if not s:
            return None
        val = s.pop(0) if srcpos == "LEFT" else s.pop()
        d = self._list(dst)
        d.append(val) if dstpos == "RIGHT" else d.insert(0, val)
        return val

    def blmove(self, src, dst, timeout, srcpos="LEFT", dstpos="RIGHT"):
        return self._move(src, dst, srcpos, dstpos)

    def lmove(self, src, dst, srcpos="LEFT", dstpos="RIGHT"):
        return self._move(src, dst, srcpos, dstpos)

    def lrem(self, key, count, value):
        v = value if isinstance(value, bytes) else str(value).encode()
        lst = self._list(key)
        removed = 0
        i = 0
        while i < len(lst):
            if lst[i] == v and (count == 0 or removed < count):
                lst.pop(i)
                removed += 1
            else:
                i += 1
        return removed

    def llen(self, key):
        return len(self._list(key))

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key, ttl):
        self.expires[key] = ttl

    def rpush(self, key, value):
        self.pushed.append((key, value))
        self._list(key).append(str(value).encode())


def test_process_success_uses_lang_text():
    sf = _factory()
    job_id, audio_id = _seed(sf, lang="ja")
    seen = {}

    def synth(audio, text):
        seen["text"] = text
        seen["lang"] = audio.lang
        return f"/data/audio/{audio.id}.wav"

    AudioWorker(sf, FakeRedis([]), synth).process(job_id)

    assert seen["text"] == "日本語のテキスト"  # ja -> poem_ja
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.DONE
        a = s.get(Audio, audio_id)
        assert a.status == AssetStatus.DONE
        assert a.path == f"/data/audio/{audio_id}.wav"


def test_english_uses_poem_en():
    sf = _factory()
    job_id, _ = _seed(sf, lang="en")
    seen = {}
    AudioWorker(sf, FakeRedis([]), lambda a, t: seen.setdefault("t", t) or "/x.wav").process(job_id)
    assert seen["t"] == "english text"


def test_failure_dead_letters_without_retries():
    sf = _factory()
    job_id, audio_id = _seed(sf)

    def synth(audio, text):
        raise RuntimeError("piper boom")

    AudioWorker(sf, FakeRedis([]), synth, max_retries=0).process(job_id)
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED
        assert "piper boom" in s.get(Job, job_id).error
        assert s.get(Audio, audio_id).status == AssetStatus.FAILED


def test_unsupported_language_fails_fast_without_retry():
    from app.voices import UnsupportedLanguageError

    sf = _factory()
    job_id, audio_id = _seed(sf, lang="ja")
    redis = FakeRedis()

    def synth(audio, text):
        raise UnsupportedLanguageError("set TTS_BACKEND=xtts for Japanese")

    # max_retries=1, but an unsupported-language error must NOT be re-enqueued.
    worker = AudioWorker(sf, redis, synth, max_retries=1)
    assert worker.process(job_id) is False  # no re-enqueue
    assert redis.pushed == []
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED
        assert "xtts" in s.get(Job, job_id).error
        assert s.get(Audio, audio_id).status == AssetStatus.FAILED


def test_failure_retries_then_dead_letters():
    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis()

    def synth(audio, text):
        raise RuntimeError("boom")

    worker = AudioWorker(sf, redis, synth, max_retries=1)
    assert worker.process(job_id) is True  # 1st failure -> wants re-enqueue
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED
    assert redis.pushed == []  # process does not re-enqueue directly
    assert redis.expires.get(f"retry:audio:{job_id}")  # retry counter has a TTL
    assert worker.process(job_id) is False  # 2nd failure -> dead-letter
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED


def test_run_once_reliable_delivery_requeue_and_ack():
    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis([job_id])

    def synth(audio, text):
        raise RuntimeError("boom")

    worker = AudioWorker(sf, redis, synth, max_retries=1)
    assert worker.run_once() is True
    # Failed job re-enqueued; processing list cleared (acked).
    assert redis.pushed == [("jobs:audio", job_id)]
    assert redis.llen("jobs:audio") == 1
    assert redis.llen("jobs:audio:processing") == 0
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED


def test_run_once_consumes():
    sf = _factory()
    job_id, _ = _seed(sf)
    worker = AudioWorker(sf, FakeRedis([job_id]), lambda a, t: "/data/audio/x.wav")
    assert worker.run_once() is True
    assert worker.run_once() is False
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.DONE


def test_idempotent_skip_done():
    sf = _factory()
    job_id, _ = _seed(sf)
    with sf() as s:
        s.get(Job, job_id).status = JobStatus.DONE
        s.commit()
    calls = []
    AudioWorker(sf, FakeRedis([]), lambda a, t: calls.append(1) or "x").process(job_id)
    assert calls == []
