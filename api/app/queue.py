"""Job queue abstraction (Redis-backed, with an in-memory fake for tests)."""

from __future__ import annotations

import os
from typing import Protocol


def queue_key(job_type: str) -> str:
    return f"jobs:{job_type}"


class JobQueue(Protocol):
    def enqueue(self, job_type: str, job_id: int) -> None: ...


class RedisJobQueue:
    """Pushes job ids onto per-type Redis lists (consumed by workers in M2/M3)."""

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_env(cls) -> "RedisJobQueue":
        import redis

        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        return cls(redis.Redis.from_url(url))

    def enqueue(self, job_type: str, job_id: int) -> None:
        self._client.rpush(queue_key(job_type), job_id)


class InMemoryJobQueue:
    """Test/dev queue that just records what was enqueued."""

    def __init__(self):
        self.items: dict[str, list[int]] = {}

    def enqueue(self, job_type: str, job_id: int) -> None:
        self.items.setdefault(job_type, []).append(job_id)
