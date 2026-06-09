from __future__ import annotations

import asyncio
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 5,
    backoff_base: float = 2.0,
    retryable_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504}),
) -> T:
    """
    Call async fn() with exponential backoff on failure.

    - 404 → raises immediately (not retried)
    - 429 → waits backoff_base * 2^attempt seconds before retry
    - Other exceptions → retried up to max_attempts times
    """
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except ChewyNotFoundError:
            raise
        except ChewyRateLimitError as e:
            wait = backoff_base * (2 ** attempt)
            logger.warning("Rate limited (429), waiting %.0fs before retry %d/%d",
                           wait, attempt + 1, max_attempts)
            await asyncio.sleep(wait)
            last_exc = e
        except Exception as e:
            wait = backoff_base * (2 ** attempt)
            logger.warning("Request failed (%s), waiting %.0fs before retry %d/%d",
                           type(e).__name__, wait, attempt + 1, max_attempts)
            await asyncio.sleep(wait)
            last_exc = e

    raise RuntimeError(f"Failed after {max_attempts} attempts") from last_exc


class ChewyNotFoundError(Exception):
    """Raised when Chewy returns a 404 for a product URL."""


class ChewyRateLimitError(Exception):
    """Raised when Chewy returns a 429."""
