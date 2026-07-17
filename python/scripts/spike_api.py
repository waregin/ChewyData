"""
API Discovery Spike — run this locally to find Chewy's product data.

Usage:
  python scripts/spike_api.py

Looks in two places:
  1. Network responses (XHR/fetch) — all JSON responses, not just specific keys
  2. Embedded page data — <script> tags containing JSON (Next.js __NEXT_DATA__,
     __REDUX_STATE__, window.__STATE__, etc.)

Saves findings to spike_output/ for inspection.
"""
import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

TARGET_URL = "https://www.chewy.com/ziwi-peak-air-dried-cat-food/dp/232835"
OUTPUT_DIR = Path("spike_output")

# Keys that suggest product/variant data
PRODUCT_INDICATORS = {
    "partNumber", "skuDto", "attributeValues", "advertisedPrice", "offerPrice",
    "catalogEntryId", "productId", "variants", "inventoryStatus", "listPrice",
    "salePrice", "catentryId",
}


async def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    network_hits: list[dict] = []
    all_json_urls: list[str] = []

    async def handle_response(response) -> None:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return
        try:
            body = await response.json()
        except Exception:
            return

        body_str = json.dumps(body)
        all_json_urls.append(response.url)

        if any(key in body_str for key in PRODUCT_INDICATORS):
            network_hits.append({
                "url": response.url,
                "status": response.status,
                "body": body,
            })
            print(f"  [NETWORK HIT] {response.url[:100]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.on("response", handle_response)

        print(f"Loading: {TARGET_URL}")
        print("Intercepting responses...\n")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=45_000)

        # ── Search embedded script tags ────────────────────────────────────
        print("\nSearching embedded <script> tags for JSON data...")
        script_hits: list[dict] = []

        scripts = await page.query_selector_all("script")
        for i, script in enumerate(scripts):
            content = await script.inner_text()
            if not content or len(content) < 50:
                continue

            # Look for common patterns where apps embed state
            patterns = [
                (r"__NEXT_DATA__\s*=\s*(\{.*\})", "NEXT_DATA"),
                (r"__REDUX_STATE__\s*=\s*(\{.*\})", "REDUX_STATE"),
                (r"window\.__STATE__\s*=\s*(\{.*\})", "WINDOW_STATE"),
                (r"window\.__INITIAL_STATE__\s*=\s*(\{.*\})", "INITIAL_STATE"),
                (r"window\.__PRELOADED_STATE__\s*=\s*(\{.*\})", "PRELOADED_STATE"),
            ]
            for pattern, label in patterns:
                m = re.search(pattern, content, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        script_hits.append({"label": label, "data": data})
                        print(f"  [SCRIPT HIT] Found {label} ({len(m.group(1))} chars)")
                    except json.JSONDecodeError:
                        print(f"  [SCRIPT] Found {label} pattern but JSON parse failed")

            # Also check for type="application/json" scripts
            script_type = await script.get_attribute("type")
            script_id = await script.get_attribute("id")
            if script_type == "application/json" or (script_id and "data" in script_id.lower()):
                try:
                    data = json.loads(content)
                    data_str = json.dumps(data)
                    if any(key in data_str for key in PRODUCT_INDICATORS):
                        script_hits.append({"label": f"script#{script_id or i}", "data": data})
                        print(f"  [SCRIPT HIT] <script type=application/json id={script_id}>")
                except json.JSONDecodeError:
                    pass

        # ── Raw page HTML for manual inspection ───────────────────────────
        html = await page.content()
        html_path = OUTPUT_DIR / "page.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"\n  Saved page HTML → {html_path}  ({len(html):,} chars)")

        await browser.close()

    # ── Save and report ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Network JSON responses: {len(all_json_urls)} total, "
          f"{len(network_hits)} with product indicators")
    print(f"Embedded script hits:   {len(script_hits)}")
    print(f"{'='*60}")

    if all_json_urls:
        print("\nAll JSON network URLs seen:")
        for url in all_json_urls:
            print(f"  {url[:120]}")

    for i, hit in enumerate(network_hits):
        path = OUTPUT_DIR / f"network_{i}.json"
        path.write_text(json.dumps(hit["body"], indent=2), encoding="utf-8")
        print(f"\n[Network {i}] saved → {path}")
        print(f"  URL: {hit['url']}")
        print(f"  Preview: {json.dumps(hit['body'])[:300]}")

    for i, hit in enumerate(script_hits):
        path = OUTPUT_DIR / f"script_{hit['label']}_{i}.json"
        path.write_text(json.dumps(hit["data"], indent=2), encoding="utf-8")
        print(f"\n[Script {i}] {hit['label']} saved → {path}")
        data_str = json.dumps(hit["data"])
        print(f"  Size: {len(data_str):,} chars")
        print(f"  Preview: {data_str[:300]}")

    if not network_hits and not script_hits:
        print("\nNothing found. Check spike_output/page.html manually.")
        print("Search for: partNumber, price, variant, sku, catalogEntry")


if __name__ == "__main__":
    asyncio.run(main())
