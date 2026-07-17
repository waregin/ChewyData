"""
Persistent-profile spike — free approach to getting past Chewy's bot wall.

Chewy uses KASADA (KPSDK) bot protection. A first request returns a 429 with
a JavaScript challenge (ips.js); the browser runs it, computes a token, and
re-requests automatically to get the real page. So we must WAIT for that
handshake to resolve rather than reading content off the challenge page.

Uses a dedicated, persistent Chrome profile (NOT your main profile, NOT
Guest) that keeps its Kasada cookies between runs. Run it TWICE:

  # First run — solves the challenge, saves cookies:
  python scripts/spike_persistent.py --channel chrome

  # Second run — should reuse the token / look like a returning visitor:
  python scripts/spike_persistent.py --channel chrome

--channel chrome drives your REAL installed Chrome, which passes Kasada's
JS challenge far more reliably than Playwright's bundled Chromium. Try it
first. Drop --channel to compare the bundled browser.

The profile lives in ./.chrome-profile (gitignored). Delete it to reset.
This script NEVER logs in.
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

# Kasada / Akamai challenge or block markers (transient or hard)
CHALLENGE_MARKERS = ["KPSDK", "ips.js", "KP_UIDz", "x-kpsdk"]
HARD_BLOCK_MARKERS = ["No treats beyond this point", "Served Akamai 403 WAF"]
SUCCESS_MARKERS = ["product-title", "add-to-cart", "Guaranteed Analysis",
                   "advertised-price", 'name="query"']


async def wait_for_resolution(page, timeout: float = 45.0) -> tuple[str, str]:
    """
    Poll until the Kasada challenge resolves into real content, a hard block
    appears, or we time out. Returns (outcome, html).
    outcome ∈ {"success", "blocked", "challenge_stuck", "timeout"}.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    last_html = ""
    while loop.time() < deadline:
        # Let any in-flight reload/settle
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
            # Still on the challenge page — give the JS more time to solve
            await asyncio.sleep(3)
            continue
        # No challenge, no explicit success marker, but a substantial page
        # usually means we're through to real (JS-rendered) content.
        if len(last_html) > 30_000:
            return "success", last_html
        await asyncio.sleep(3)

    return ("challenge_stuck" if any(m in last_html for m in CHALLENGE_MARKERS)
            else "timeout"), last_html


async def run(channel: str | None, headless: bool) -> None:
    profile = Path(PROFILE_DIR).resolve()
    profile.mkdir(exist_ok=True)
    print(f"\n{'='*60}")
    print("Persistent-profile spike (Kasada-aware)")
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

        # ── Step 1: Homepage — solve the challenge, get cookies ────────────
        print(f"[1] Homepage: {HOMEPAGE}")
        resp = await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=45_000)
        print(f"    initial status: {resp.status if resp else 'none'}  (429 = Kasada challenge)")
        print("    waiting for Kasada challenge to resolve...")
        outcome, _ = await wait_for_resolution(page)
        print(f"    homepage outcome: {outcome}")

        cookies = await context.cookies()
        kasada = {c["name"] for c in cookies if c["name"].startswith(("KP_", "x-kpsdk"))}
        print(f"    Kasada cookies: {sorted(kasada) or 'NONE'}")

        # ── Step 2: Product page ───────────────────────────────────────────
        print(f"\n[2] Product page: {PRODUCT_URL}")
        resp = await page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=45_000)
        print(f"    initial status: {resp.status if resp else 'none'}")
        print("    waiting for challenge to resolve...")
        outcome, html = await wait_for_resolution(page)

        Path("spike_output").mkdir(exist_ok=True)
        out = Path("spike_output") / "persistent.html"
        out.write_text(html, encoding="utf-8")

        print(f"\n{'='*60}\nRESULT\n{'='*60}")
        print(f"  HTML saved: {out}  ({len(html):,} chars)")
        print(f"  Product page outcome: {outcome}")

        if outcome == "success":
            print("\n  ✅ SUCCESS — Kasada challenge solved, real content loaded!")
            print("     Run once more to confirm it's stable, then we'll wire the")
            print("     scraper to wait for the challenge the same way.")
        elif outcome in ("challenge_stuck", "timeout"):
            print("\n  ⚠️  Challenge did NOT resolve in time.")
            if channel is None:
                print("     Try your REAL Chrome — much better vs Kasada:")
                print("     python scripts/spike_persistent.py --channel chrome")
            else:
                print("     Real Chrome couldn't solve it headed either.")
                print("     Kasada is likely blocking automation at the JS level.")
        else:
            print("\n  ❌ BLOCKED — hard block page served.")

        await context.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default=None,
                    help="Browser channel, e.g. 'chrome' for real installed Chrome (recommended)")
    ap.add_argument("--headless", action="store_true",
                    help="Run headless (default headed, which evades better)")
    args = ap.parse_args()
    asyncio.run(run(channel=args.channel, headless=args.headless))


if __name__ == "__main__":
    main()
