"""
Dump a Chewy page through the scraper's own browser layer and summarise its
structure, so parser selectors can be re-verified after a site redesign.

RUN (from ChewyData/python):
    python scripts/dump_page.py https://www.chewy.com/b/bones-1542

Saves the HTML to spike_output/dump.html and prints:
  - class names that look like product cards / pagination, with counts
  - product (/dp/) links found anywhere, and a few samples
  - the ancestor classes of the first product link (where the cards live)
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
from chewy_scraper.scraper.parsers import parse_page_urls, parse_product_urls

DP_LINK = re.compile(r"/dp/\d+")
INTERESTING = re.compile(r"product|card|tile|pagination|paging|grid|result", re.I)


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


async def main(url: str, config_path: str) -> None:
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
    summarise(html, url)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    asyncio.run(main(args.url, args.config))
