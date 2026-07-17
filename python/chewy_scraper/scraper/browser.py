"""
Playwright browser lifecycle and page factory.

Chewy is protected by Akamai Bot Manager, which serves a 403 WAF page to
obvious bots. To get through we:
  1. Launch (ideally headed — headless is the biggest tell)
  2. Apply fingerprint evasions before any page script runs
  3. Warm up on the homepage ONCE so Akamai sets/validates its cookies
     (_abck, bm_sz, ...), then reuse that warmed context for all fetches

A single shared, warmed BrowserContext is used for the whole run. Re-warming
a fresh context per request would be slow and would itself look robotic.
Concurrency within the context is bounded by the caller's semaphore.
"""
from __future__ import annotations

import asyncio
import logging

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    async_playwright,
)

from chewy_scraper.config import ScrapingConfig
from chewy_scraper.scraper.stealth import STEALTH_INIT_SCRIPT
from chewy_scraper.utils.retry import ChewyNotFoundError, ChewyRateLimitError

logger = logging.getLogger(__name__)

_playwright: Playwright | None = None
_browser: Browser | None = None
_context: BrowserContext | None = None


async def start_browser(config: ScrapingConfig) -> None:
    """Launch the browser, build one stealthed context, and warm it up."""
    global _playwright, _browser, _context

    _playwright = await async_playwright().start()
    launch_args = [
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    proxy = {"server": config.proxy_url} if config.proxy_url else None

    _browser = await _playwright.chromium.launch(
        headless=config.headless,
        args=launch_args,
        proxy=proxy,
    )

    ua = config.user_agents[0] if config.user_agents else None
    _context = await _browser.new_context(
        user_agent=ua,
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        },
    )
    if config.stealth:
        await _context.add_init_script(STEALTH_INIT_SCRIPT)

    # Block images/fonts/media (NOT scripts — Akamai's sensor JS must run)
    await _context.route("**/*", _block_non_essential)

    await _warm_up(config)


async def _warm_up(config: ScrapingConfig) -> None:
    """Visit the homepage so Akamai sets and validates its cookies."""
    if _context is None:
        return
    page = await _context.new_page()
    try:
        logger.info("Warming up on %s ...", config.warmup_url)
        await page.goto(config.warmup_url, wait_until="domcontentloaded", timeout=45_000)
        # Human-like scroll while the sensor JS runs
        for _ in range(int(config.warmup_pause)):
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(1)
        cookies = await _context.cookies()
        akamai = {c["name"] for c in cookies} & {"_abck", "bm_sz", "ak_bmsc"}
        logger.info("Warm-up complete. Akamai cookies: %s", sorted(akamai) or "NONE")
    finally:
        await page.close()


async def stop_browser() -> None:
    global _playwright, _browser, _context
    if _context:
        await _context.close()
        _context = None
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


async def _block_non_essential(route: Route, request) -> None:
    if request.resource_type in {"image", "font", "media"}:
        await route.abort()
    else:
        await route.continue_()


async def fetch_page_html(url: str, config: ScrapingConfig) -> str:
    """
    Open a new page in the shared warmed context, navigate, return HTML.
    Raises ChewyNotFoundError on 404, ChewyRateLimitError on 429.
    """
    if _context is None:
        raise RuntimeError("Browser not started — call start_browser() first")

    page = await _context.new_page()
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if response is None:
            raise RuntimeError(f"No response for {url}")
        if response.status == 404:
            raise ChewyNotFoundError(url)
        if response.status == 429:
            raise ChewyRateLimitError(url)
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status} for {url}")

        html = await page.content()
        # Detect Akamai block page even when it returns HTTP 200
        if "No treats beyond this point" in html or "Served Akamai 403 WAF" in html:
            raise ChewyRateLimitError(f"Akamai block page for {url}")
        return html
    finally:
        await page.close()
