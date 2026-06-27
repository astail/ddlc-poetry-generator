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
    redis = FakeRedis([])

    def proc(image):
        raise RuntimeError("boom")

    worker = ImageWorker(sf, redis, proc, max_retries=1)

    worker.process(job_id)  # 1st failure -> re-enqueued
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.QUEUED
    assert redis.pushed == [("jobs:image", job_id)]

    worker.process(job_id)  # 2nd failure -> dead-letter
    with sf() as s:
        assert s.get(Job, job_id).status == JobStatus.FAILED
        assert s.get(Image, image_id).status == AssetStatus.FAILED


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
