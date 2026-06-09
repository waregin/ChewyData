"""
Category-level crawling: paginate through a listing page and collect
all product URLs for that category.
"""
from __future__ import annotations

import asyncio
import logging

from chewy_scraper.config import CategoryConfig, ScrapingConfig
from chewy_scraper.scraper.browser import fetch_page_html
from chewy_scraper.scraper.parsers import parse_page_urls, parse_product_urls
from chewy_scraper.utils.rate_limiter import RateLimiter
from chewy_scraper.utils.retry import ChewyNotFoundError, with_retry

logger = logging.getLogger(__name__)


async def collect_product_urls(
    category: CategoryConfig,
    config: ScrapingConfig,
    limiter: RateLimiter,
) -> list[str]:
    """
    Return all unique product URLs across all pages of a category listing.
    """
    await limiter.wait()
    base_html = await with_retry(
        lambda: fetch_page_html(category.url, config),
        max_attempts=config.retry_max_attempts,
        backoff_base=config.retry_backoff_base,
    )

    product_urls = parse_product_urls(base_html)
    page_urls = parse_page_urls(base_html, category.url)

    logger.info(
        "Category '%s': page 1 has %d products, %d more pages",
        category.name, len(product_urls), len(page_urls),
    )

    # Fetch remaining pages concurrently (respecting semaphore in browser module)
    sem = asyncio.Semaphore(config.concurrency)

    async def fetch_page(url: str) -> list[str]:
        async with sem:
            await limiter.wait()
            try:
                html = await with_retry(
                    lambda: fetch_page_html(url, config),
                    max_attempts=config.retry_max_attempts,
                    backoff_base=config.retry_backoff_base,
                )
                return parse_product_urls(html)
            except ChewyNotFoundError:
                logger.warning("404 on page URL: %s", url)
                return []

    results = await asyncio.gather(*[fetch_page(u) for u in page_urls])
    for batch in results:
        product_urls.extend(batch)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for url in product_urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)

    logger.info("Category '%s': %d total unique products", category.name, len(deduped))
    return deduped
