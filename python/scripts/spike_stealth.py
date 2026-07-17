"""
Stealth Spike — test whether we can get past Chewy's Akamai bot protection.

Chewy serves an Akamai WAF 403 block page to headless browsers. This script
tries several free anti-detection techniques and reports whether each gets
real product content or the block page.

Usage:
  # Headed mode (recommended first attempt — headless is the biggest tell):
  python scripts/spike_stealth.py

  # Force headless to compare:
  python scripts/spike_stealth.py --headless

Techniques applied:
  1. Fingerprint evasions (navigator.webdriver, plugins, WebGL, etc.)
  2. Homepage warm-up so Akamai sets/validates its _abck + bm_sz cookies
  3. Human-like pacing (scroll, delays) before reading the product page
  4. Realistic browser context (viewport, locale, timezone, headers)

If HEADED mode gets through but HEADLESS doesn't, run the real scraper with
headless=False. If NEITHER works, the free path is exhausted and you'll need
residential proxies or a commercial unblocker.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Allow running as a plain script without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

from chewy_scraper.scraper.stealth import DEFAULT_STEALTH_UA, STEALTH_INIT_SCRIPT

HOMEPAGE = "https://www.chewy.com"
PRODUCT_URL = "https://www.chewy.com/ziwi-peak-air-dried-cat-food/dp/232835"

# Signals that we hit the Akamai block page rather than real content
BLOCK_SIGNALS = [
    "No treats beyond this point",
    "Akamai",
    "restricted access",
    "Page error: 403",
]
# Signals that we actually reached a real product page
SUCCESS_SIGNALS = [
    "product-title",
    "add-to-cart",
    "Guaranteed Analysis",
    "advertised-price",
]


async def human_pause(page, seconds: float) -> None:
    """Wait while doing a little human-like scrolling."""
    steps = max(1, int(seconds))
    for _ in range(steps):
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(1)


async def run(headless: bool) -> None:
    print(f"\n{'='*60}")
    print(f"Stealth spike — mode: {'HEADLESS' if headless else 'HEADED'}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=DEFAULT_STEALTH_UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        page = await context.new_page()

        # ── Step 1: Warm up on the homepage ────────────────────────────────
        print(f"[1] Warming up on homepage: {HOMEPAGE}")
        try:
            resp = await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=45_000)
            print(f"    Homepage status: {resp.status if resp else 'no response'}")
        except Exception as e:
            print(f"    Homepage load error: {e}")

        # Let Akamai's sensor JS run and set/validate cookies
        print("    Pausing to let Akamai cookies settle (human-like scroll)...")
        await human_pause(page, 4)

        cookies = await context.cookies()
        cookie_names = {c["name"] for c in cookies}
        akamai_cookies = cookie_names & {"_abck", "bm_sz", "ak_bmsc", "bm_mi", "bm_sv"}
        print(f"    Akamai cookies present: {sorted(akamai_cookies) or 'NONE'}")

        # ── Step 2: Navigate to the product page ───────────────────────────
        print(f"\n[2] Navigating to product page: {PRODUCT_URL}")
        try:
            resp = await page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=45_000)
            print(f"    Product page status: {resp.status if resp else 'no response'}")
        except Exception as e:
            print(f"    Product page load error: {e}")

        await human_pause(page, 3)

        # ── Step 3: Analyse what we got ────────────────────────────────────
        html = await page.content()
        Path("spike_output").mkdir(exist_ok=True)
        out = Path("spike_output") / f"stealth_{'headless' if headless else 'headed'}.html"
        out.write_text(html, encoding="utf-8")

        blocked = any(sig in html for sig in BLOCK_SIGNALS)
        succeeded = any(sig in html for sig in SUCCESS_SIGNALS)

        print(f"\n{'='*60}")
        print("RESULT")
        print(f"{'='*60}")
        print(f"  HTML saved to: {out}  ({len(html):,} chars)")
        print(f"  Block-page signals found:   {blocked}")
        print(f"  Product-content signals:    {succeeded}")

        if succeeded and not blocked:
            print("\n  ✅ SUCCESS — reached real product content!")
            print(f"     Run the scraper with headless={headless}.")
        elif blocked:
            print("\n  ❌ BLOCKED — Akamai served the WAF page.")
            if headless:
                print("     Try again WITHOUT --headless (headed mode).")
            else:
                print("     Headed + stealth + warm-up still blocked.")
                print("     Free path likely exhausted → residential proxy / unblocker.")
        else:
            print("\n  ⚠️  UNCLEAR — no clear block or success signals.")
            print(f"     Inspect {out} manually.")

        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (default is headed, which evades better)")
    args = parser.parse_args()
    asyncio.run(run(headless=args.headless))


if __name__ == "__main__":
    main()
