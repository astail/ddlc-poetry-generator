"""FastAPI dependency providers (overridable in tests)."""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from .claude_client import PoemGenerator
from .db import create_db_engine, make_session_factory
from .queue import JobQueue, RedisJobQueue
from .ratelimit import RateLimiter, RateLimiterLike, RedisRateLimiter


@lru_cache
def _session_factory():
    return make_session_factory(create_db_engine())


def get_session() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_generator() -> PoemGenerator:
    return PoemGenerator()


@lru_cache
def get_queue() -> JobQueue:
    return RedisJobQueue.from_env()


def get_data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


@lru_cache
def get_rate_limiter() -> RateLimiterLike:
    max_per_min = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
    if os.environ.get("REDIS_URL"):
        # Shared across processes/replicas (#135). redis_from_url is lazy, and a
        # runtime Redis outage fails open in RedisRateLimiter.check.
        from .queue import redis_from_url

        return RedisRateLimiter(redis_from_url(), max_per_min, 60)
    return RateLimiter(max_per_min, 60)


@lru_cache
def get_generation_semaphore() -> threading.BoundedSemaphore:
    """Caps concurrent in-flight poem generations (#59).

    ``POST /api/generate`` runs as a sync handler in FastAPI's threadpool and
    blocks for the whole (slow) Claude call. Without a cap, enough concurrent
    generations exhaust the threadpool and starve every other endpoint. This
    bounds how many run at once (GENERATE_MAX_CONCURRENCY, default 4); requests
    over the cap get a fast 503 instead of piling up.
    """
    return threading.BoundedSemaphore(int(os.environ.get("GENERATE_MAX_CONCURRENCY", "4")))


def get_api_auth_token() -> str | None:
    """Optional shared secret; when set, POST /api/generate requires it."""
    return os.environ.get("API_AUTH_TOKEN") or None
