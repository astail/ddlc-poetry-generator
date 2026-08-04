"""Simple in-memory sliding-window rate limiter (issue #20).

Scope / limitations (see #57): state is per-process and in-memory, so the
effective limit across multiple uvicorn workers / replicas is roughly
``max_requests * process_count``. For a shared, replica-consistent limit,
``RedisRateLimiter`` below (fixed window ``INCR``+``EXPIRE``, #135) is selected
automatically when ``REDIS_URL`` is set. The key is whatever the caller passes:
the API keys on the caller's *name* when one is configured (see
``NamedClientLimiter`` and ``app.clients``) and otherwise on
``request.client.host``. Behind a reverse proxy the latter is the gateway IP
unless uvicorn runs with ``--proxy-headers``/``--forwarded-allow-ips`` — which
is exactly why a named bucket is the better lever for a proxied deployment.

Memory is bounded: expired buckets are reclaimed and the number of tracked keys
is capped (``max_keys``) so a flood of distinct keys can't grow the map without
limit (memory-exhaustion DoS).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

from redis.exceptions import RedisError

from .clients import ClientRegistry

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


class NamedClientLimiter:
    """Per-*name* buckets for the callers listed in ``RATE_LIMIT_CLIENTS``.

    Maps a peer IP to a configured name (docker compose service name, hostname,
    IP or CIDR — see ``app.clients``) and hands back that name plus a limiter
    carrying the name's own limit. Callers that match nothing get ``None`` and
    the API falls back to the default per-IP bucket, so this is inert until an
    operator configures it.

    Limiters are built lazily and one per name, since each may have a different
    ``max_requests``; a Redis-backed limiter keys on the name too, so all
    replicas share the bucket.
    """

    def __init__(
        self,
        registry: ClientRegistry,
        limiter_factory: Callable[[int], RateLimiterLike],
        default_max: int,
    ):
        self._registry = registry
        self._factory = limiter_factory
        self._default_max = default_max
        self._limiters: dict[str, RateLimiterLike] = {}
        self._lock = threading.Lock()

    def for_peer(self, peer_ip: str | None) -> tuple[str, RateLimiterLike] | None:
        """Return ``(name, limiter)`` for a configured caller, else ``None``."""
        rule = self._registry.match(peer_ip)
        if rule is None:
            return None
        with self._lock:
            limiter = self._limiters.get(rule.name)
            if limiter is None:
                limiter = self._factory(rule.max_per_min or self._default_max)
                self._limiters[rule.name] = limiter
        return rule.name, limiter
