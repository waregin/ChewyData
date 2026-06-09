from __future__ import annotations

import asyncio
import random


class RateLimiter:
    """
    Asyncio-safe delay between requests with random jitter.
    All concurrent tasks share one limiter instance so they
    don't all fire at the same moment.
    """

    def __init__(self, min_delay: float, max_delay: float) -> None:
        self._min = min_delay
        self._max = max_delay
        self._lock = asyncio.Lock()
        self._last_release: float = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            delay = random.uniform(self._min, self._max)
            elapsed = now - self._last_release
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            self._last_release = asyncio.get_event_loop().time()
