"""Security utilities for postal-inspector.

This module provides rate limiting and other security-related
utilities used throughout the application.
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, max_per_minute: int = 30):
        self.max_per_minute = max_per_minute
        self.timestamps: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until rate limit allows another request."""
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)

            # Remove old timestamps
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()

            # Wait if at limit
            if len(self.timestamps) >= self.max_per_minute:
                wait_time = (self.timestamps[0] + timedelta(minutes=1) - now).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Re-check after waiting
                    now = datetime.now()
                    cutoff = now - timedelta(minutes=1)
                    while self.timestamps and self.timestamps[0] < cutoff:
                        self.timestamps.popleft()

            self.timestamps.append(now)

    @property
    def current_count(self) -> int:
        """Current number of requests in the window."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        return sum(1 for ts in self.timestamps if ts > cutoff)
