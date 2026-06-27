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
    def __init__(self, items):
        self.items = list(items)
        self.counters = {}
        self.pushed = []

    def blpop(self, keys, timeout=0):
        if self.items:
            return (keys[0].encode(), str(self.items.pop(0)).encode())
        return None

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def rpush(self, key, value):
        self.pushed.append((key, value))
        self.items.append(value)


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
    AudioWorker(sf, FakeRedis([]), lambda a, t: seen.setdefault("t", t) or "/x.wav").process(
        job_id
    )
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


def test_failure_retries_then_dead_letters():
    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis([])

    def synth(audio, text):
        raise RuntimeError("boom")

    worker = AudioWorker(sf, redis, synth, max_retries=1)
    worker.process(job_id)
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED
    assert redis.pushed == [("jobs:audio", job_id)]
    worker.process(job_id)
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED


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
