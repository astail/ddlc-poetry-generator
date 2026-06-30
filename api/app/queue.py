"""Job queue abstraction (Redis-backed, with an in-memory fake for tests)."""

from __future__ import annotations

import os
from typing import Optional, Protocol


def queue_key(job_type: str) -> str:
    return f"jobs:{job_type}"


def redis_from_url(url: Optional[str] = None):
    """Build a Redis client hardened against idle-connection drops.

    Docker's NAT silently drops idle TCP connections, so the worker's long-lived
    blocking-pop connection would eventually fail the next call with "Timeout
    reading from socket". When that landed on the ack / retry-bookkeeping path it
    stranded jobs (RUNNING forever, parked on the processing list). socket
    keepalive + periodic health checks + retry-on-timeout keep the connection
    healthy and recover from transient blips.
    """
    import redis

    return redis.Redis.from_url(
        url or os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        socket_keepalive=True,
        health_check_interval=30,
        retry_on_timeout=True,
    )


class JobQueue(Protocol):
    def enqueue(self, job_type: str, job_id: int) -> None: ...


class RedisJobQueue:
    """Pushes job ids onto per-type Redis lists (consumed by workers in M2/M3)."""

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisJobQueue":
        return cls(redis_from_url())

    def enqueue(self, job_type: str, job_id: int) -> None:
        self._client.rpush(queue_key(job_type), job_id)


class InMemoryJobQueue:
    """Test/dev queue that just records what was enqueued."""

    def __init__(self):
        self.items: dict[str, list[int]] = {}

    def enqueue(self, job_type: str, job_id: int) -> None:
        self.items.setdefault(job_type, []).append(job_id)
