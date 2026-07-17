"""
Playwright browser lifecycle and page factory.

Chewy is protected by Akamai Bot Manager. Our free strategy:

  1. Drive a PERSISTENT, dedicated Chrome profile (its own user_data_dir) —
     NOT your main profile (account-safety) and NOT Guest (Guest forgets
     cookies). The profile keeps its Akamai cookies (_abck, bm_sz, ...)
     between runs so you look like a returning human, not a fresh bot.
  2. Optionally use your REAL installed Chrome (channel="chrome") for a more
     authentic fingerprint than the bundled Chromium.
  3. Headed by default (headless is the single biggest detection signal).
  4. Warm up on the homepage once so Akamai validates the profile's cookies.
  5. Fingerprint evasions injected before any page script runs.
  6. Gentle, serial pacing (see config) — never burst.

The scraper NEVER logs in. All data is the public catalog, so scraping
cannot be tied to your Chewy customer account.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright, Route, async_playwright

from chewy_scraper.config import ScrapingConfig
from chewy_scraper.scraper.stealth import STEALTH_INIT_SCRIPT
from chewy_scraper.utils.retry import ChewyNotFoundError, ChewyRateLimitError

logger = logging.getLogger(__name__)

_playwright: Playwright | None = None
_context: BrowserContext | None = None


async def start_browser(config: ScrapingConfig) -> None:
    """Launch a persistent, stealthed Chrome profile and warm it up."""
    global _playwright, _context

    _playwright = await async_playwright().start()

    profile_path = Path(config.profile_dir).expanduser().resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    logger.info("Using persistent profile: %s", profile_path)

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    proxy = {"server": config.proxy_url} if config.proxy_url else None
    ua = config.user_agents[0] if config.user_agents else None

    # launch_persistent_context returns the context directly (no separate
    # Browser object) — the profile on disk IS the browser state.
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=config.headless,
        channel=config.browser_channel,   # None → bundled Chromium
        args=launch_args,
        proxy=proxy,
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
    """Visit the homepage so Akamai sets/validates cookies for this profile."""
    if _context is None:
        return
    page = await _context.new_page()
    try:
        logger.info("Warming up on %s ...", config.warmup_url)
        resp = await page.goto(config.warmup_url, wait_until="domcontentloaded", timeout=45_000)
        status = resp.status if resp else "no response"
        for _ in range(int(config.warmup_pause)):
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(1)
        cookies = await _context.cookies()
        akamai = {c["name"] for c in cookies} & {"_abck", "bm_sz", "ak_bmsc"}
        logger.info("Warm-up status=%s, Akamai cookies: %s", status, sorted(akamai) or "NONE")
        if status == 429 or not akamai:
            logger.warning(
                "Warm-up did not establish Akamai cookies. If fetches fail, "
                "wait a while (429s are temporary) or try browser_channel='chrome'."
            )
    finally:
        await page.close()


async def stop_browser() -> None:
    global _playwright, _context
    if _context:
        await _context.close()
        _context = None
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
    Open a new page in the shared persistent context, navigate, return HTML.
    Raises ChewyNotFoundError on 404, ChewyRateLimitError on 429/WAF block.
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
        # Akamai sometimes serves the block page with a 200 status
        if "No treats beyond this point" in html or "Served Akamai 403 WAF" in html:
            raise ChewyRateLimitError(f"Akamai block page for {url}")
        return html
    finally:
        await page.close()
