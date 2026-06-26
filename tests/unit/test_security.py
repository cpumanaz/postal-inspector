"""Tests for security module."""

import pytest

from postal_inspector.core.logging import sanitize_for_log
from postal_inspector.core.security import RateLimiter


def test_sanitize_for_log_removes_control_chars():
    assert sanitize_for_log("hello\x00world") == "helloworld"


def test_sanitize_for_log_truncates():
    long_text = "x" * 200
    assert len(sanitize_for_log(long_text, 50)) == 50


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(max_per_minute=10)
    for _ in range(5):
        await limiter.acquire()
    assert limiter.current_count == 5


@pytest.mark.asyncio
async def test_rate_limiter_property():
    limiter = RateLimiter(max_per_minute=30)
    await limiter.acquire()
    await limiter.acquire()
    assert limiter.current_count == 2
