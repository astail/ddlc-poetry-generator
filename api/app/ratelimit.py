"""Simple in-memory sliding-window rate limiter (issue #20).

Scope / limitations (see #57): state is per-process and in-memory, so the
effective limit across multiple uvicorn workers / replicas is roughly
``max_requests * process_count``. For a shared, replica-consistent limit,
``RedisRateLimiter`` below (fixed window ``INCR``+``EXPIRE``, #135) is selected
automatically when ``REDIS_URL`` is set. The key is whatever the caller passes (the API uses ``request.client.host``); behind
a reverse proxy run uvicorn with ``--proxy-headers``/``--forwarded-allow-ips``
so that resolves to the real client rather than the gateway IP.

Memory is bounded: expired buckets are reclaimed and the number of tracked keys
is capped (``max_keys``) so a flood of distinct keys can't grow the map without
limit (memory-exhaustion DoS).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DEFAULT_MAX_KEYS = 10_000


class RateLimiterLike(Protocol):
    """Shared interface: ``check(key) -> (allowed, retry_after_seconds)``."""

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]: ...


class RateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        max_keys: int = DEFAULT_MAX_KEYS,
    ):
        self.max = max_requests
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.max:
                retry_after = int(self.window - (now - hits[0])) + 1
                self._hits[key] = hits
                return False, retry_after
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > self.max_keys:
                self._evict(now)
            return True, 0

    def _evict(self, now: float) -> None:
        """Bound memory: drop expired buckets, then oldest active ones if needed.

        Called only when the key count exceeds ``max_keys``. First reclaim
        buckets whose newest hit has aged out of the window (cheap, no behaviour
        change for live clients). If still over the cap — i.e. genuinely many
        *active* keys, e.g. a distinct-IP flood — drop those closest to expiry
        (oldest last-hit) until under the cap. The just-inserted key carries a
        ``now`` timestamp, so it is never the one evicted.
        """
        expired = [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]
        for k in expired:
            del self._hits[k]
        overflow = len(self._hits) - self.max_keys
        if overflow > 0:
            oldest = sorted(self._hits.items(), key=lambda kv: kv[1][-1])[:overflow]
            for k, _ in oldest:
                del self._hits[k]


class RedisRateLimiter:
    """Fixed-window rate limiter shared across processes via Redis (#135).

    Follow-up to #57's per-process in-memory limiter: each ``(key, window)`` is a
    single Redis ``INCR`` with an ``EXPIRE``, so all uvicorn workers / replicas
    share one counter and the effective limit is the real ``max_requests``
    regardless of process count. On a Redis error it **fails open** (allows the
    request) rather than locking out legitimate traffic on a transient blip — the
    cost it guards (Claude / GPU) is already bounded by ``GENERATE_MAX_CONCURRENCY``.
    """

    def __init__(self, client, max_requests: int, window_seconds: float):
        self._client = client
        self.max = max_requests
        self.window = window_seconds

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Uses wall-clock ``time.time`` so
        the window boundary is consistent across processes."""
        now = time.time() if now is None else now
        window_index = int(now // self.window)
        redis_key = f"ratelimit:{key}:{window_index}"
        try:
            count = int(self._client.incr(redis_key))
            if count == 1:
                # Expire just after the window closes so counters self-clean.
                self._client.expire(redis_key, int(self.window) + 1)
        except (RedisError, OSError):
            logger.warning("rate limiter Redis unavailable; allowing request (fail-open)")
            return True, 0
        if count > self.max:
            retry_after = int(self.window - (now % self.window)) + 1
            return False, retry_after
        return True, 0
