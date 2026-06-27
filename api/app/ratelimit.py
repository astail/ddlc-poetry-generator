"""Simple in-memory sliding-window rate limiter (issue #20)."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max = max_requests
        self.window = window_seconds
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
            return True, 0
