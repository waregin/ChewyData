"""
Patchright spike — last high-quality FREE attempt against Chewy's Kasada wall.

Our persistent-profile spike proved Kasada detects the AUTOMATION itself:
vanilla Playwright drives Chrome over CDP, and Kasada spots CDP-driven
sessions (e.g. the Runtime.enable leak a human browser never triggers), so
it keeps re-serving the challenge no matter how real the browser looks.

Patchright (https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) is a patched
drop-in replacement for Playwright that suppresses those CDP leaks. Same API.

SETUP (one time):
    pip install patchright
    patchright install chromium      # installs a patched Chromium

RUN (twice, real Chrome recommended):
    python scripts/spike_patchright.py --channel chrome
    python scripts/spike_patchright.py --channel chrome

    # or bundled patched Chromium:
    python scripts/spike_patchright.py

Uses the SAME persistent profile dir as the other spike (.chrome-profile).
NEVER logs in.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    # Patchright is a drop-in replacement — identical API surface.
    from patchright.async_api import async_playwright
    ENGINE = "patchright"
except ImportError:
    print("Patchright is not installed. Install it first:\n")
    print("    pip install patchright")
    print("    patchright install chromium\n")
    sys.exit(1)

from chewy_scraper.scraper.stealth import DEFAULT_STEALTH_UA

HOMEPAGE = "https://www.chewy.com"
PRODUCT_URL = "https://www.chewy.com/ziwi-peak-air-dried-cat-food/dp/232835"
PROFILE_DIR = ".chrome-profile-patchright"   # separate profile from the vanilla spike

CHALLENGE_MARKERS = ["KPSDK", "ips.js", "KP_UIDz", "x-kpsdk"]
HARD_BLOCK_MARKERS = ["No treats beyond this point", "Served Akamai 403 WAF"]
SUCCESS_MARKERS = ["product-title", "add-to-cart", "Guaranteed Analysis",
                   "advertised-price", 'name="query"']


async def wait_for_resolution(page, timeout: float = 45.0) -> tuple[str, str]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    last_html = ""
    while loop.time() < deadline:
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass
        last_html = await page.content()
        if any(m in last_html for m in HARD_BLOCK_MARKERS):
            return "blocked", last_html
        if any(m in last_html for m in SUCCESS_MARKERS):
            return "success", last_html
        if any(m in last_html for m in CHALLENGE_MARKERS):
            await asyncio.sleep(3)
            continue
        if len(last_html) > 30_000:
            return "success", last_html
        await asyncio.sleep(3)
    return ("challenge_stuck" if any(m in last_html for m in CHALLENGE_MARKERS)
            else "timeout"), last_html


async def run(channel: str | None, headless: bool) -> None:
    profile = Path(PROFILE_DIR).resolve()
    profile.mkdir(exist_ok=True)
    print(f"\n{'='*60}")
    print(f"Patchright spike (engine: {ENGINE})")
    print(f"  profile: {profile}")
    print(f"  channel: {channel or 'patched chromium'}")
    print(f"  mode:    {'headless' if headless else 'headed'}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        # Patchright recommends: persistent context, no custom UA, no extra
        # init scripts (its patches handle stealth), channel=chrome, headed.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=headless,
            channel=channel,
            no_viewport=True,
        )
        page = await context.new_page()

        print(f"[1] Homepage: {HOMEPAGE}")
        resp = await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=45_000)
        print(f"    initial status: {resp.status if resp else 'none'}")
        print("    waiting for Kasada challenge to resolve...")
        outcome, _ = await wait_for_resolution(page)
        print(f"    homepage outcome: {outcome}")

        cookies = await context.cookies()
        kasada = {c["name"] for c in cookies if c["name"].startswith(("KP_", "x-kpsdk"))}
        print(f"    Kasada cookies: {sorted(kasada) or 'NONE'}")

        print(f"\n[2] Product page: {PRODUCT_URL}")
        resp = await page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=45_000)
        print(f"    initial status: {resp.status if resp else 'none'}")
        print("    waiting for challenge to resolve...")
        outcome, html = await wait_for_resolution(page)

        Path("spike_output").mkdir(exist_ok=True)
        out = Path("spike_output") / "patchright.html"
        out.write_text(html, encoding="utf-8")

        print(f"\n{'='*60}\nRESULT\n{'='*60}")
        print(f"  HTML saved: {out}  ({len(html):,} chars)")
        print(f"  Product page outcome: {outcome}")

        if outcome == "success":
            print("\n  ✅ SUCCESS — Patchright got through Kasada!")
            print("     This is the winning setup. Tell me and I'll switch the")
            print("     scraper's browser layer to patchright + this config.")
        elif outcome in ("challenge_stuck", "timeout"):
            print("\n  ⚠️  Still stuck.")
            if channel is None:
                print("     Try real Chrome: python scripts/spike_patchright.py --channel chrome")
            else:
                print("     Patchright + real Chrome couldn't solve Kasada either.")
                print("     This is the honest end of the free road.")
        else:
            print("\n  ❌ Hard block served.")

        await context.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default=None,
                    help="e.g. 'chrome' for real installed Chrome (recommended)")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(channel=args.channel, headless=args.headless))


if __name__ == "__main__":
    main()
