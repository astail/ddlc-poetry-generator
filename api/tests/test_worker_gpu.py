from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AssetStatus, Base, Image, Job, JobStatus, JobType, Poem
from app.worker_gpu import ImageWorker


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _seed(sf):
    with sf() as s:
        poem = Poem(character="yuri", title="t", poem_en="e", poem_ja="j")
        image = Image(prompt="p")
        poem.images.append(image)
        s.add(poem)
        s.flush()
        job = Job(type=JobType.IMAGE, ref_id=image.id)
        s.add(job)
        s.commit()
        return job.id, image.id


class FakeRedis:
    """Minimal Redis double supporting the reliable-delivery list ops (#58)."""

    def __init__(self, queue=(), queue_name="jobs:image"):
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


def test_process_success_sets_paths_and_status():
    sf = _factory()
    job_id, image_id = _seed(sf)
    calls = []

    def proc(image):
        calls.append(image.id)
        return "/data/images/out.png"

    ImageWorker(sf, FakeRedis([]), proc).process(job_id)

    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.DONE
        img = s.get(Image, image_id)
        assert img.status == AssetStatus.DONE
        assert img.path == "/data/images/out.png"
    assert calls == [image_id]


def test_process_failure_dead_letters_without_retries():
    sf = _factory()
    job_id, image_id = _seed(sf)

    def proc(image):
        raise RuntimeError("boom")

    ImageWorker(sf, FakeRedis([]), proc, max_retries=0).process(job_id)

    with sf() as s:
        job = s.get(Job, job_id)
        assert job.status == JobStatus.FAILED
        assert "boom" in job.error
        assert s.get(Image, image_id).status == AssetStatus.FAILED


def test_failure_retries_then_dead_letters():
    sf = _factory()
    job_id, image_id = _seed(sf)
    redis = FakeRedis()

    def proc(image):
        raise RuntimeError("boom")

    worker = ImageWorker(sf, redis, proc, max_retries=1)

    # process now only sets status + returns whether to re-enqueue (the run loop
    # does the rpush after commit); it must NOT push itself.
    assert worker.process(job_id) is True  # 1st failure -> wants re-enqueue
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED
    assert redis.pushed == []  # process does not re-enqueue directly
    assert redis.expires.get(f"retry:image:{job_id}")  # retry counter has a TTL

    assert worker.process(job_id) is False  # 2nd failure -> dead-letter
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED
        assert s.get(Image, image_id).status == AssetStatus.FAILED


def test_run_once_requeues_failed_job_after_commit():
    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis([job_id])

    def proc(image):
        raise RuntimeError("boom")

    worker = ImageWorker(sf, redis, proc, max_retries=1)
    assert worker.run_once() is True
    # Re-enqueued back onto the queue, and the in-flight processing list is clear.
    assert redis.pushed == [("jobs:image", job_id)]
    assert redis.llen("jobs:image:processing") == 0
    assert redis.llen("jobs:image") == 1
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED


def test_run_once_acks_processing_list_on_success():
    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis([job_id])
    worker = ImageWorker(sf, redis, lambda i: "/data/x.png")
    assert worker.run_once() is True
    # Job consumed and removed from BOTH the queue and the processing list.
    assert redis.llen("jobs:image") == 0
    assert redis.llen("jobs:image:processing") == 0
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.DONE


def test_reaper_requeues_stuck_processing_jobs():
    from app.worker_common import reap_stuck

    sf = _factory()
    job_id, _ = _seed(sf)
    redis = FakeRedis([job_id])
    # Simulate a crash: the id is parked on the processing list, never acked.
    raw = redis.blmove("jobs:image", "jobs:image:processing", 0)
    assert raw is not None
    assert redis.llen("jobs:image:processing") == 1
    assert redis.llen("jobs:image") == 0

    assert reap_stuck(redis, "image") == 1
    # Recovered back onto the queue so it gets reprocessed (at-least-once).
    assert redis.llen("jobs:image") == 1
    assert redis.llen("jobs:image:processing") == 0


def test_idempotent_skips_done_jobs():
    sf = _factory()
    job_id, _ = _seed(sf)
    with sf() as s:
        s.get(Job, job_id).status = JobStatus.DONE
        s.commit()
    calls = []
    ImageWorker(sf, FakeRedis([]), lambda i: calls.append(1) or "x").process(job_id)
    assert calls == []


def test_run_once_consumes_then_empty():
    sf = _factory()
    job_id, _ = _seed(sf)
    worker = ImageWorker(sf, FakeRedis([job_id]), lambda i: "/data/x.png")
    assert worker.run_once() is True
    assert worker.run_once() is False
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.DONE


def test_missing_job_does_not_crash():
    sf = _factory()
    ImageWorker(sf, FakeRedis([]), lambda i: "x").process(99999)
