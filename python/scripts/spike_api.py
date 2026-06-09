"""
API Discovery Spike — run this locally to find Chewy's internal API.

Usage:
  PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers python scripts/spike_api.py

What it does:
  1. Opens a Chewy product page in a headless browser
  2. Intercepts ALL network responses during page load
  3. Filters for JSON responses that look like product/SKU data
  4. Prints the URLs and a sample of each response body

If you find an endpoint that returns variant/SKU data as JSON (like the
sample in tests/fixtures/data.json), update API_ENDPOINT_TEMPLATE in
chewy_scraper/scraper/api_client.py with the URL pattern.
"""
import asyncio
import json
import re

from playwright.async_api import async_playwright

# A product page that has multiple size/count variants — good for testing
TARGET_URL = "https://www.chewy.com/ziwi-peak-air-dried-cat-food/dp/232835"

# We're looking for JSON responses that contain product/SKU-like keys
SKU_INDICATORS = {"partNumber", "skuDto", "attributeValues", "advertisedPrice", "offerPrice"}


async def main() -> None:
    captured: list[dict] = []

    async def handle_response(response) -> None:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return
        try:
            body = await response.json()
        except Exception:
            return

        body_str = json.dumps(body)
        if any(key in body_str for key in SKU_INDICATORS):
            captured.append({
                "url": response.url,
                "status": response.status,
                "body_preview": body_str[:500],
                "full_body": body,
            })
            print(f"\n[MATCH] {response.url}")
            print(f"  Status: {response.status}")
            print(f"  Preview: {body_str[:300]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.on("response", handle_response)

        print(f"Loading: {TARGET_URL}")
        print("Intercepting network responses...\n")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=30_000)

        await browser.close()

    print(f"\n\n{'='*60}")
    print(f"Found {len(captured)} matching JSON response(s)")
    print(f"{'='*60}")
    for i, hit in enumerate(captured, 1):
        print(f"\n[{i}] {hit['url']}")

    if captured:
        print("\n\nTo save the first match for analysis:")
        print("  Uncomment the lines below and re-run\n")
        # with open("tests/fixtures/spike_output.json", "w") as f:
        #     json.dump(captured[0]["full_body"], f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
