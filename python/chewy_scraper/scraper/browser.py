"""
Playwright browser lifecycle and page factory.

A single Browser is shared across all concurrent scraping tasks.
Each task gets its own BrowserContext (isolated cookies/storage) and
Page so they don't interfere with each other.
"""
from __future__ import annotations

import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    async_playwright,
)

from chewy_scraper.config import ScrapingConfig
from chewy_scraper.utils.retry import ChewyNotFoundError, ChewyRateLimitError


_playwright: Playwright | None = None
_browser: Browser | None = None


async def start_browser(config: ScrapingConfig) -> None:
    global _playwright, _browser
    _playwright = await async_playwright().start()
    launch_args = [
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    if config.proxy_url:
        proxy = {"server": config.proxy_url}
    else:
        proxy = None

    _browser = await _playwright.chromium.launch(
        headless=True,
        args=launch_args,
        proxy=proxy,
    )


async def stop_browser() -> None:
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


@asynccontextmanager
async def new_page(config: ScrapingConfig) -> AsyncGenerator[Page, None]:
    """
    Yield an isolated Page with a randomised User-Agent and stealth headers.
    The context (and page) are closed when the context manager exits.
    """
    if _browser is None:
        raise RuntimeError("Browser not started — call start_browser() first")

    ua = random.choice(config.user_agents)
    context: BrowserContext = await _browser.new_context(
        user_agent=ua,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    # Block image/font/media downloads to speed up page loads
    await context.route(
        "**/*",
        lambda route, request: _block_non_essential(route, request),
    )
    page = await context.new_page()
    try:
        yield page
    finally:
        await context.close()


async def _block_non_essential(route: Route, request) -> None:
    if request.resource_type in {"image", "font", "media"}:
        await route.abort()
    else:
        await route.continue_()


async def fetch_page_html(url: str, config: ScrapingConfig) -> str:
    """
    Navigate to url, wait for network idle, and return the full page HTML.
    Raises ChewyNotFoundError on 404, ChewyRateLimitError on 429.
    """
    async with new_page(config) as page:
        response = await page.goto(url, wait_until="networkidle", timeout=30_000)
        if response is None:
            raise RuntimeError(f"No response for {url}")
        if response.status == 404:
            raise ChewyNotFoundError(url)
        if response.status == 429:
            raise ChewyRateLimitError(url)
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return await page.content()
