"""
Patchright browser lifecycle and page factory.

Chewy is protected by Kasada, which detects the AUTOMATION itself: vanilla
Playwright drives Chrome over CDP, and Kasada spots CDP-driven sessions
(e.g. the Runtime.enable leak) no matter how real the browser looks.

Patchright (https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) is a patched
drop-in replacement for Playwright that suppresses those leaks. Proven
setup (scripts/spike_patchright.py, two clean runs):

  1. Patchright driving REAL installed Chrome (channel="chrome"), headed.
  2. A PERSISTENT, dedicated profile (its own user_data_dir) — NOT your main
     profile (account-safety) and NOT Guest (Guest forgets cookies). It keeps
     Kasada's KP_UIDz cookies between runs, so later runs skip the challenge.
  3. NO custom user agent, headers, viewport, launch flags or init scripts.
     Patchright's patches handle stealth; overriding the fingerprint by hand
     creates mismatches (e.g. a Mac UA on Linux Chrome) that Kasada flags.
  4. Kasada answers a fresh session with a 429 challenge page whose JS solves
     itself and reloads. That 429 is NOT a rate limit — we wait it out.
  5. Gentle, serial pacing (see config) — never burst.

The scraper NEVER logs in. All data is the public catalog, so scraping
cannot be tied to your Chewy customer account.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from patchright.async_api import BrowserContext, Page, Playwright, Route, async_playwright

from chewy_scraper.config import ScrapingConfig
from chewy_scraper.utils.retry import ChewyNotFoundError, ChewyRateLimitError

logger = logging.getLogger(__name__)

_playwright: Playwright | None = None
_context: BrowserContext | None = None

# Present on Kasada's interstitial challenge page while it is solving.
CHALLENGE_MARKERS = ("KPSDK", "ips.js", "KP_UIDz", "x-kpsdk")
# Hard block pages (no challenge to solve — back off).
HARD_BLOCK_MARKERS = ("No treats beyond this point", "Served Akamai 403 WAF")
# Present on real Chewy pages (search box is on every page).
SUCCESS_MARKERS = ("product-title", "add-to-cart", "Guaranteed Analysis",
                   "advertised-price", 'name="query"')
KASADA_COOKIE_PREFIXES = ("KP_", "x-kpsdk")


async def start_browser(config: ScrapingConfig) -> None:
    """Launch Patchright on a persistent profile and pass Kasada once."""
    global _playwright, _context

    _playwright = await async_playwright().start()

    profile_path = Path(config.profile_dir).expanduser().resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    logger.info("Using persistent profile: %s", profile_path)

    proxy = {"server": config.proxy_url} if config.proxy_url else None

    # launch_persistent_context returns the context directly (no separate
    # Browser object) — the profile on disk IS the browser state.
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=config.headless,
        channel=config.browser_channel,   # None → Patchright's bundled Chromium
        proxy=proxy,
        no_viewport=True,
    )

    if config.block_resources:
        # Off by default: the proven setup loaded everything. Scripts are never
        # blocked — Kasada's challenge JS must run.
        await _context.route("**/*", _block_non_essential)

    await _warm_up(config)


async def _warm_up(config: ScrapingConfig) -> None:
    """Visit the homepage so Kasada issues/validates this profile's cookies."""
    if _context is None:
        return
    page = await _context.new_page()
    try:
        logger.info("Warming up on %s ...", config.warmup_url)
        resp = await page.goto(config.warmup_url, wait_until="domcontentloaded", timeout=45_000)
        status = resp.status if resp else "no response"
        outcome, _ = await _wait_for_resolution(page, config.challenge_timeout)
        for _ in range(int(config.warmup_pause)):
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(1)
        cookies = await _context.cookies()
        kasada = {c["name"] for c in cookies if c["name"].startswith(KASADA_COOKIE_PREFIXES)}
        logger.info("Warm-up status=%s outcome=%s, Kasada cookies: %s",
                    status, outcome, sorted(kasada) or "NONE")
        if outcome != "success" or "KP_UIDz" not in kasada:
            logger.warning(
                "Warm-up did not pass Kasada. If fetches fail, wait a while "
                "and make sure browser_channel is 'chrome' and headless is false."
            )
    finally:
        await page.close()


async def _wait_for_resolution(page: Page, timeout: float) -> tuple[str, str]:
    """
    Poll the page until Kasada's challenge resolves.

    Returns (outcome, html) where outcome is one of:
    "success", "blocked", "challenge_stuck", "timeout".
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    html = ""
    while loop.time() < deadline:
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass
        try:
            html = await page.content()
        except Exception:
            # Content can't be read mid-navigation (the challenge reloads the page).
            await asyncio.sleep(1)
            continue
        if any(m in html for m in HARD_BLOCK_MARKERS):
            return "blocked", html
        if any(m in html for m in SUCCESS_MARKERS):
            return "success", html
        if not any(m in html for m in CHALLENGE_MARKERS) and len(html) > 30_000:
            return "success", html
        await asyncio.sleep(3)
    outcome = "challenge_stuck" if any(m in html for m in CHALLENGE_MARKERS) else "timeout"
    return outcome, html


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

    A 429 on first load is usually Kasada's challenge, so it is waited out
    rather than raised. Raises ChewyNotFoundError on 404, and
    ChewyRateLimitError on a block page or a challenge that never resolves.
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
        if response.status >= 400 and response.status != 429:
            raise RuntimeError(f"HTTP {response.status} for {url}")

        outcome, html = await _wait_for_resolution(page, config.challenge_timeout)
        if outcome != "success":
            raise ChewyRateLimitError(
                f"{outcome} for {url} (initial status {response.status})"
            )
        return html
    finally:
        await page.close()
