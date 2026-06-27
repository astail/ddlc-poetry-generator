"""Shared worker failure handling: retry with re-enqueue, then dead-letter (#20)."""

from __future__ import annotations

import logging

from .models import AssetStatus, Job, JobStatus
from .queue import queue_key

logger = logging.getLogger(__name__)


def handle_job_failure(
    redis_client,
    job: Job,
    asset,
    exc: Exception,
    *,
    job_type: str,
    max_retries: int,
) -> bool:
    """Re-enqueue a failed job up to max_retries, else dead-letter it.

    Returns True if the job was dead-lettered (terminal), False if re-enqueued.
    Mutates job/asset status; caller commits the session.
    """
    attempts = int(redis_client.incr(f"retry:{job_type}:{job.id}"))
    if attempts <= max_retries:
        job.status = JobStatus.QUEUED
        asset.status = AssetStatus.PENDING
        job.error = f"retry {attempts}/{max_retries}: {exc}"[:500]
        redis_client.rpush(queue_key(job_type), job.id)
        logger.warning("job %s failed, re-enqueued (attempt %s)", job.id, attempts)
        return False

    job.status = JobStatus.FAILED
    asset.status = AssetStatus.FAILED
    job.error = str(exc)[:500]
    logger.error("job %s dead-lettered after %s attempts", job.id, attempts)
    return True
