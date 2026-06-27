"""Unit tests for the in-memory rate limiter, incl. bounded memory (#57)."""

from app.ratelimit import RateLimiter


def test_allows_up_to_max_then_blocks():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.check("ip", now=0) == (True, 0)
    assert rl.check("ip", now=1) == (True, 0)
    allowed, retry_after = rl.check("ip", now=2)
    assert allowed is False
    assert retry_after > 0


def test_window_slides_and_allows_again():
    rl = RateLimiter(max_requests=1, window_seconds=10)
    assert rl.check("ip", now=0)[0] is True
    assert rl.check("ip", now=5)[0] is False  # still inside window
    assert rl.check("ip", now=11)[0] is True  # first hit aged out


def test_per_key_isolation():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    assert rl.check("a", now=0)[0] is True
    assert rl.check("b", now=0)[0] is True  # different key, own bucket
    assert rl.check("a", now=0)[0] is False


def test_expired_buckets_are_reclaimed_when_over_cap():
    # Old keys that never come back must not linger once we exceed the cap.
    rl = RateLimiter(max_requests=5, window_seconds=10, max_keys=3)
    for i in range(3):
        rl.check(f"old-{i}", now=0)
    assert len(rl._hits) == 3
    # A new key past the window triggers eviction of the (now expired) old ones.
    rl.check("fresh", now=100)
    assert "fresh" in rl._hits
    assert all(k == "fresh" for k in rl._hits)  # expired keys reclaimed
    assert len(rl._hits) <= rl.max_keys


def test_key_count_is_capped_under_active_flood():
    # Many *active* distinct keys within the window: memory stays bounded.
    rl = RateLimiter(max_requests=5, window_seconds=1000, max_keys=10)
    for i in range(100):
        rl.check(f"ip-{i}", now=float(i))
    assert len(rl._hits) <= rl.max_keys
    # The most recently seen key is always retained (never evicted itself).
    assert "ip-99" in rl._hits
