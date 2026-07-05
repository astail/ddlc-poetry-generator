"""Shared worker queue mechanics + failure handling (#20, hardened in #58).

Delivery is at-least-once: a job is atomically moved from its queue onto a
per-type *processing* list while in flight (``BLMOVE``), and only removed once
the worker is done with it (``LREM`` ack). If a worker is killed mid-job the id
is left on the processing list and a startup *reaper* moves it back to the queue
so the asset doesn't stay ``pending`` forever. Re-enqueue on retry happens only
after the DB status is committed (see the worker run loops), closing the
double-processing window that existed when ``rpush`` ran before ``commit``.
"""

from __future__ import annotations

import logging
import os

from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from .models import AssetStatus, Job, JobStatus
from .queue import queue_key

logger = logging.getLogger(__name__)

# How long a retry counter lives before Redis drops it, so the keys don't
# accumulate forever for ids that never come back.
RETRY_TTL_SECONDS = 24 * 60 * 60

# How often the worker loop re-runs maintenance (reaping stuck processing-list
# ids). The startup pass only catches a *previous* worker's leftovers; running it
# periodically also recovers ids this worker stranded on a mid-job Redis blip
# without waiting for a restart.
MAINTENANCE_INTERVAL_SECONDS = 60


def processing_key(job_type: str) -> str:
    """Redis list holding ids a worker has popped but not yet finished."""
    return f"{queue_key(job_type)}:processing"


def heartbeat_path(job_type: str, data_dir=None):
    """Path of the per-worker heartbeat file under the data dir (#127)."""
    from pathlib import Path

    base = Path(data_dir if data_dir is not None else os.environ.get("DATA_DIR", "/data"))
    return base / f".worker_{job_type}.heartbeat"


def write_heartbeat(job_type: str, data_dir=None) -> None:
    """Touch the heartbeat file so a container healthcheck can tell the worker's
    consume loop is alive (#127). Best-effort: a write failure is logged, never
    fatal to the loop."""
    path = heartbeat_path(job_type, data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError:
        logger.warning("could not write %s worker heartbeat", job_type)


def reliable_pop(redis_client, job_type: str, timeout: int):
    """Block for one job, atomically moving it queue -> processing list.

    Returns the raw id (bytes) still parked on the processing list, or None on
    timeout. The caller must ``ack`` it once the job is fully handled.
    """
    try:
        return redis_client.blmove(
            queue_key(job_type), processing_key(job_type), timeout, "LEFT", "RIGHT"
        )
    except RedisTimeoutError:
        # A socket-read timeout while blocking on an *empty* queue just means
        # "nothing arrived this window" — redis-py's read deadline races the
        # server-side block timeout. Treat it as no job rather than spamming the
        # loop's error handler. An item that was actually moved but whose reply
        # was lost stays on the processing list and the periodic reaper recovers
        # it, so nothing is dropped.
        return None


def ack(redis_client, job_type: str, raw) -> None:
    """Remove a finished id from the processing list (it's no longer in flight)."""
    redis_client.lrem(processing_key(job_type), 1, raw)


def reap_stuck(redis_client, job_type: str) -> int:
    """Requeue ids left on the processing list by a previously-killed worker.

    Runs at startup. Returns how many ids were recovered. With one worker per
    queue type (the default deployment) this is safe; for multiple concurrent
    workers a per-worker processing list / visibility timeout would be needed.
    """
    recovered = 0
    while True:
        moved = redis_client.lmove(processing_key(job_type), queue_key(job_type), "LEFT", "LEFT")
        if moved is None:
            break
        recovered += 1
        logger.warning("reaped stuck %s job %r back to queue", job_type, moved)
    if recovered:
        logger.warning("reaper recovered %s stuck %s job(s)", recovered, job_type)
    return recovered


def reconcile_orphans(redis_client, session_factory, job_type: str, statuses=None) -> int:
    """Re-enqueue jobs the DB still has as queued/running but that are gone from
    Redis. Runs at startup and, QUEUED-only, periodically from the worker loop.

    Redis is not the source of truth for *which* jobs exist (the DB is), and the
    queue can be lost out from under it — a Redis restart with no/late snapshot,
    ``docker compose down -v``, or the API crashing right after committing a job
    but before the enqueue (#126). When that happens the ids vanish from the
    lists but the DB rows stay queued/running, so the worker never sees them again
    and the asset is stuck pending/running forever. This pushes any such id back
    onto the queue so it gets processed.

    ``statuses`` selects which DB job states are eligible (default: QUEUED +
    RUNNING — the full recovery run, safe at startup *before* the consume loop).
    The periodic in-loop call passes ``(QUEUED,)`` only, so a job actively in
    flight (RUNNING and already parked on the processing list) is never
    re-enqueued and double-processed. Assumes a single worker per queue type.
    """
    from sqlalchemy import select

    from .models import Job, JobStatus

    if statuses is None:
        statuses = (JobStatus.QUEUED, JobStatus.RUNNING)

    in_redis: set[int] = set()
    for key in (queue_key(job_type), processing_key(job_type)):
        for raw in redis_client.lrange(key, 0, -1):
            try:
                in_redis.add(int(raw))
            except (ValueError, TypeError):
                continue

    recovered = 0
    with session_factory() as session:
        stmt = select(Job.id).where(
            Job.type == job_type,
            Job.status.in_(list(statuses)),
        )
        for job_id in session.execute(stmt).scalars():
            if job_id not in in_redis:
                redis_client.rpush(queue_key(job_type), job_id)
                recovered += 1
    if recovered:
        logger.warning("reconciled %s orphaned %s job(s) back onto the queue", recovered, job_type)
    return recovered


def handle_job_failure(
    redis_client,
    job: Job,
    asset,
    exc: Exception,
    *,
    job_type: str,
    max_retries: int,
) -> bool:
    """Mark a failed job for retry (up to max_retries) or dead-letter it.

    Returns True if the job should be re-enqueued (the caller does the actual
    ``rpush`` *after* committing the status), False if it was dead-lettered.
    Mutates job/asset status only; the caller commits the session.
    """
    try:
        attempts = int(redis_client.incr(f"retry:{job_type}:{job.id}"))
        redis_client.expire(f"retry:{job_type}:{job.id}", RETRY_TTL_SECONDS)
    except (RedisError, OSError):
        # Redis is unreachable. We can't track the attempt count, and a
        # re-enqueue would need Redis too, so dead-letter to a terminal, visible
        # state. Previously any exception here escaped before the caller's commit,
        # stranding the job RUNNING on the processing list until the next restart.
        # (Builtin ConnectionError is an OSError, so test/double failures match.)
        logger.exception("retry bookkeeping unavailable for %s job %s; failing", job_type, job.id)
        job.status = JobStatus.FAILED
        asset.status = AssetStatus.FAILED
        job.error = f"{exc} [retry tracking unavailable]"[:500]
        return False
    if attempts <= max_retries:
        job.status = JobStatus.QUEUED
        asset.status = AssetStatus.PENDING
        job.error = f"retry {attempts}/{max_retries}: {exc}"[:500]
        logger.warning("job %s failed, will re-enqueue (attempt %s)", job.id, attempts)
        return True

    job.status = JobStatus.FAILED
    asset.status = AssetStatus.FAILED
    job.error = str(exc)[:500]
    logger.error("job %s dead-lettered after %s attempts", job.id, attempts)
    return False
