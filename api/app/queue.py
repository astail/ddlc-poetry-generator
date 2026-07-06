"""Job queue abstraction (Redis-backed, with an in-memory fake for tests)."""

from __future__ import annotations

import os
from typing import Protocol


def queue_key(job_type: str) -> str:
    return f"jobs:{job_type}"


def redis_from_url(url: str | None = None):
    """Build a Redis client hardened against transient connection failures.

    The worker holds a long-lived connection for its blocking-pop loop, and two
    distinct things go wrong on it (both historically surfaced as "Timeout
    reading from socket"):

    1. A Docker/NAT idle drop on a rarely-used connection — addressed here with
       TCP keepalive (tuned via ``socket_keepalive_options``; bare
       ``socket_keepalive`` falls back to the OS default idle time of ~2h, too
       long to help) plus a pre-command ``health_check``.
    2. A blocking ``BLMOVE``'s read deadline racing its own server-side block
       timeout on an empty queue — that one is benign and is handled where it
       belongs, in ``reliable_pop``.

    The ``retry`` below covers the non-blocking ops (rpush/incr/lrem/lrange) so a
    one-off blip doesn't bubble up to the loop's error handler.
    """
    import socket

    import redis
    from redis.backoff import ExponentialBackoff
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError
    from redis.retry import Retry

    # Only the keepalive knobs the running platform actually defines (Linux has
    # TCP_KEEPIDLE/INTVL/CNT; they're absent on e.g. macOS dev machines).
    keepalive_options = {}
    for name, value in (("TCP_KEEPIDLE", 60), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3)):
        opt = getattr(socket, name, None)
        if opt is not None:
            keepalive_options[opt] = value

    return redis.Redis.from_url(
        url or os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        socket_keepalive=True,
        socket_keepalive_options=keepalive_options,
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(cap=10, base=0.5), retries=3),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    )


class JobQueue(Protocol):
    def enqueue(self, job_type: str, job_id: int) -> None: ...
    def ping(self) -> None: ...


class RedisJobQueue:
    """Pushes job ids onto per-type Redis lists (consumed by workers in M2/M3)."""

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_env(cls) -> RedisJobQueue:
        return cls(redis_from_url())

    def enqueue(self, job_type: str, job_id: int) -> None:
        self._client.rpush(queue_key(job_type), job_id)

    def ping(self) -> None:
        # Round-trip to Redis so /health can report backend reachability (#127).
        self._client.ping()


class InMemoryJobQueue:
    """Test/dev queue that just records what was enqueued."""

    def __init__(self):
        self.items: dict[str, list[int]] = {}

    def enqueue(self, job_type: str, job_id: int) -> None:
        self.items.setdefault(job_type, []).append(job_id)

    def ping(self) -> None:
        return None
