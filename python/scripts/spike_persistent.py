"""
Persistent-profile spike — the free approach to getting past Akamai.

Uses a dedicated, persistent Chrome profile (NOT your main profile, NOT
Guest) that keeps its Akamai cookies between runs. Run it TWICE:

  # First run — establishes the profile's cookies:
  python scripts/spike_persistent.py

  # Second run a minute later — should look like a returning visitor:
  python scripts/spike_persistent.py

  # Try your REAL Chrome (more authentic fingerprint) if bundled fails:
  python scripts/spike_persistent.py --channel chrome

The profile is stored in ./.chrome-profile (gitignored). Delete that folder
to start fresh. This script NEVER logs in.

If the second run reaches real product content, set in config.yaml:
  scraping.headless: false
  scraping.profile_dir: ".chrome-profile"
  scraping.browser_channel: "chrome"   # only if you used --channel chrome
...and the real scraper will work the same way.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

from chewy_scraper.scraper.stealth import DEFAULT_STEALTH_UA, STEALTH_INIT_SCRIPT

HOMEPAGE = "https://www.chewy.com"
PRODUCT_URL = "https://www.chewy.com/ziwi-peak-air-dried-cat-food/dp/232835"
PROFILE_DIR = ".chrome-profile"

BLOCK_SIGNALS = ["No treats beyond this point", "Served Akamai 403 WAF", "Page error: 403"]
SUCCESS_SIGNALS = ["product-title", "add-to-cart", "Guaranteed Analysis", "advertised-price"]


async def human_pause(page, seconds: int) -> None:
    for _ in range(seconds):
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(1)


async def run(channel: str | None, headless: bool) -> None:
    profile = Path(PROFILE_DIR).resolve()
    profile.mkdir(exist_ok=True)
    print(f"\n{'='*60}")
    print(f"Persistent-profile spike")
    print(f"  profile: {profile}")
    print(f"  channel: {channel or 'bundled chromium'}")
    print(f"  mode:    {'headless' if headless else 'headed'}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=headless,
            channel=channel,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
            user_agent=DEFAULT_STEALTH_UA if channel is None else None,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            },
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)

        page = await context.new_page()

        print(f"[1] Homepage warm-up: {HOMEPAGE}")
        resp = await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=45_000)
        print(f"    status: {resp.status if resp else 'none'}")
        await human_pause(page, 4)

        cookies = await context.cookies()
        akamai = {c["name"] for c in cookies} & {"_abck", "bm_sz", "ak_bmsc"}
        print(f"    Akamai cookies: {sorted(akamai) or 'NONE'}")

        print(f"\n[2] Product page: {PRODUCT_URL}")
        resp = await page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=45_000)
        print(f"    status: {resp.status if resp else 'none'}")
        await human_pause(page, 3)

        html = await page.content()
        Path("spike_output").mkdir(exist_ok=True)
        out = Path("spike_output") / "persistent.html"
        out.write_text(html, encoding="utf-8")

        blocked = any(s in html for s in BLOCK_SIGNALS)
        succeeded = any(s in html for s in SUCCESS_SIGNALS)

        print(f"\n{'='*60}\nRESULT\n{'='*60}")
        print(f"  HTML saved: {out}  ({len(html):,} chars)")
        print(f"  Blocked:    {blocked}")
        print(f"  Succeeded:  {succeeded}")
        if succeeded and not blocked:
            print("\n  ✅ SUCCESS — reached real product content!")
            print("     Run a 2nd time to confirm the returning-visitor effect,")
            print("     then configure the real scraper (see this file's docstring).")
        elif blocked:
            print("\n  ❌ BLOCKED — Akamai served the WAF page.")
            print("     Try: run again in a minute (cookies may warm up),")
            print("     or:  python scripts/spike_persistent.py --channel chrome")
        else:
            print(f"\n  ⚠️  UNCLEAR — inspect {out} manually.")

        await context.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default=None,
                    help="Browser channel, e.g. 'chrome' to use real installed Chrome")
    ap.add_argument("--headless", action="store_true",
                    help="Run headless (default headed, which evades better)")
    args = ap.parse_args()
    asyncio.run(run(channel=args.channel, headless=args.headless))


if __name__ == "__main__":
    main()
