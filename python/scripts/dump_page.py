"""
Dump a Chewy page through the scraper's own browser layer and summarise its
structure, so parser selectors can be re-verified after a site redesign.

RUN (from ChewyData/python):
    python scripts/dump_page.py https://www.chewy.com/b/bones-1542
    python scripts/dump_page.py --product https://www.chewy.com/some-item/dp/551934
    python scripts/dump_page.py --product --file spike_output/patchright.html   # no fetch

Category mode saves the HTML to spike_output/dump.html and prints:
  - class names that look like product cards / pagination, with counts
  - product (/dp/) links found anywhere, and a few samples
  - the ancestor classes of the first product link (where the cards live)

Product mode (--product) prints what the product parser extracts today, the
variant-picker-like elements, and where SKU data sits in embedded JSON.
"""
import argparse
import asyncio
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup

from chewy_scraper.config import load_config
from chewy_scraper.scraper import browser
from chewy_scraper.scraper.parsers import (
    SEL_CHIP_OPTION,
    parse_page_urls,
    parse_product_page,
    parse_product_urls,
)

DP_LINK = re.compile(r"/dp/\d+")
INTERESTING = re.compile(r"product|card|tile|pagination|paging|grid|result", re.I)
VARIANT_LIKE = re.compile(r"chip|variant|option|size|swatch|attribute|choice|selector|radio", re.I)
SKU_KEYS = ("partNumber", "attributeValues", "skus", "variants", "catalogEntryId", "itemId")


def summarise(html: str, url: str) -> None:
    soup = BeautifulSoup(html, "lxml")
    print(f"\nTitle: {soup.title.get_text(strip=True) if soup.title else '?'}")
    print(f"Current parser: {len(parse_product_urls(html))} product URLs, "
          f"{len(parse_page_urls(html, url))} extra pages")

    classes: Counter[str] = Counter()
    testids: Counter[str] = Counter()
    for el in soup.find_all(True):
        for c in el.get("class", []):
            if INTERESTING.search(c):
                classes[c] += 1
        tid = el.get("data-testid")
        if tid and INTERESTING.search(tid):
            testids[tid] += 1
    print("\nCard/pagination-like classes (top 30):")
    for c, n in classes.most_common(30):
        print(f"  {n:4d}  {c}")
    print("\nCard/pagination-like data-testid values (top 20):")
    for t, n in testids.most_common(20):
        print(f"  {n:4d}  {t}")

    links = [a["href"] for a in soup.find_all("a", href=True) if DP_LINK.search(a["href"])]
    print(f"\n/dp/ links: {len(links)} total, {len(set(links))} unique. Samples:")
    for href in list(dict.fromkeys(links))[:5]:
        print(f"  {href}")

    first = next((a for a in soup.find_all("a", href=True) if DP_LINK.search(a["href"])), None)
    if first is not None:
        print("\nAncestors of the first /dp/ link (innermost first):")
        for parent in list(first.parents)[:8]:
            attrs = " ".join(parent.get("class", []))
            tid = parent.get("data-testid", "")
            print(f"  <{parent.name}> class='{attrs[:90]}' data-testid='{tid}'")

    page_links = [a["href"] for a in soup.find_all("a", href=True)
                  if re.search(r"[_?&/]p(age)?[=_]?\d+", a["href"]) and "/b/" in a["href"]]
    print(f"\nPagination-looking links: {list(dict.fromkeys(page_links))[:6]}")


def _describe(el) -> str:
    cls = " ".join(el.get("class", []))[:70]
    attrs = {k: v for k, v in el.attrs.items()
             if k in ("data-testid", "value", "aria-label", "name", "role", "href")}
    text = el.get_text(" ", strip=True)[:40]
    return f"<{el.name}> class='{cls}' {attrs} text='{text}'"


def summarise_product(html: str) -> None:
    soup = BeautifulSoup(html, "lxml")
    print(f"\nTitle: {soup.title.get_text(strip=True) if soup.title else '?'}")
    parsed = parse_product_page(html)
    if parsed is None:
        print("Current parser: no product-title block found")
    else:
        print("Current parser:")
        print(f"  brand={parsed.brand_name!r} item={parsed.item_name!r}")
        print(f"  price={parsed.price_str!r} image={'yes' if parsed.image_url else 'no'}")
        print(f"  ingredients={'yes' if parsed.ingredients_text else 'no'} "
              f"nutrition_rows={len(parsed.nutrition)} "
              f"feeding={'yes' if parsed.feeding_instructions else 'no'}")
        print(f"  options ({len(parsed.options)}): "
              f"{[(o.sku, o.label) for o in parsed.options[:8]]}")

    chips = soup.find_all(class_=SEL_CHIP_OPTION)
    print(f"\nElements with the old chip class ({len(chips)}). First 3 and their ancestors:")
    for chip in chips[:3]:
        print(f"  {_describe(chip)}")
        for parent in list(chip.parents)[:6]:
            print(f"      ^ <{parent.name}> class='{' '.join(parent.get('class', []))[:70]}' "
                  f"data-testid='{parent.get('data-testid', '')}'")

    classes: Counter[str] = Counter()
    testids: Counter[str] = Counter()
    for el in soup.find_all(True):
        for c in el.get("class", []):
            if VARIANT_LIKE.search(c):
                classes[c] += 1
        tid = el.get("data-testid")
        if tid and VARIANT_LIKE.search(tid):
            testids[tid] += 1
    print("\nVariant-like classes (top 25):")
    for c, n in classes.most_common(25):
        print(f"  {n:4d}  {c}")
    print("\nVariant-like data-testid values (top 20), first element of each:")
    for t, n in testids.most_common(20):
        print(f"  {n:4d}  {t}: {_describe(soup.find(attrs={'data-testid': t}))}")

    print("\nEmbedded scripts mentioning SKU-ish keys (first 6):")
    matching = [s for s in soup.find_all("script")
                if any(k in (s.string or "") for k in SKU_KEYS)]
    print(f"  {len(matching)} matching scripts")
    for script in matching[:6]:
        body = script.string or ""
        hits = {k: body.count(k) for k in SKU_KEYS if k in body}
        if hits:
            ident = script.get("id") or script.get("type") or "inline"
            print(f"  [{ident}] {len(body):,} chars, {hits}")
            key = next(iter(hits))
            i = body.index(key)
            print(f"      ...{body[max(0, i - 150):i + 250]}...")


async def fetch(url: str, config_path: str) -> str:
    cfg = load_config(config_path).scraping
    await browser.start_browser(cfg)
    try:
        html = await browser.fetch_page_html(url, cfg)
    finally:
        await browser.stop_browser()
    out = Path("spike_output") / "dump.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Saved {out} ({len(html):,} chars)")
    return html


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default="")
    ap.add_argument("--product", action="store_true", help="summarise a product page")
    ap.add_argument("--file", help="read saved HTML instead of fetching")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    if args.file:
        page_html = Path(args.file).read_text(encoding="utf-8")
    elif args.url:
        page_html = asyncio.run(fetch(args.url, args.config))
    else:
        ap.error("give a URL or --file")
    if args.product:
        summarise_product(page_html)
    else:
        summarise(page_html, args.url)
