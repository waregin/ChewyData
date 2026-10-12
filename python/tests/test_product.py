"""scrape_product_variants against the Oct 2026 product page, with fetching stubbed."""
import re
from pathlib import Path

from chewy_scraper.config import CategoryConfig, ScrapingConfig
from chewy_scraper.scraper import product
from chewy_scraper.utils.rate_limiter import RateLimiter

PDP_HTML = (Path(__file__).parent / "fixtures" / "pdp_next_data.html").read_text()
PRODUCT_URL = "https://www.chewy.com/chewy-peanut-butter-filled-dog-treat/dp/1819678"


async def test_variants_fetched_by_part_number_without_refetching_base(monkeypatch):
    fetched: list[str] = []

    async def fake_fetch(url, config):
        fetched.append(url)
        return PDP_HTML

    monkeypatch.setattr(product, "fetch_page_html", fake_fetch)
    variants = await product.scrape_product_variants(
        product_url=PRODUCT_URL,
        category=CategoryConfig(name="Bones", url="https://www.chewy.com/b/bones-1542"),
        all_allergens={},
        config=ScrapingConfig(),
        limiter=RateLimiter(0, 0),
        seen_skus=set(),
    )

    assert fetched[0] == PRODUCT_URL
    assert len(fetched) == 9          # base page + 8 other variants
    assert "https://www.chewy.com/chewy-peanut-butter-filled-dog-treat/dp/1819710" in fetched
    assert len(variants) == 9
    base = next(v for v in variants if v.sku == "1819678")
    assert base.price_cents == 699
    assert base.option_label == "Peanut Butter, 1 count"


async def test_variant_urls_use_entry_id_not_part_number(monkeypatch):
    # Older products (e.g. Grillerz) have entryID != partNumber, and only the
    # entryID resolves as /dp/<id>. Simulate that by offsetting every entryID.
    html = re.sub(r'"entryID": "(\d+)"',
                  lambda m: f'"entryID": "{int(m.group(1)) + 1}"', PDP_HTML)
    fetched: list[str] = []

    async def fake_fetch(url, config):
        fetched.append(url)
        return html

    monkeypatch.setattr(product, "fetch_page_html", fake_fetch)
    variants = await product.scrape_product_variants(
        product_url=PRODUCT_URL,
        category=CategoryConfig(name="Bones", url="https://www.chewy.com/b/bones-1542"),
        all_allergens={},
        config=ScrapingConfig(),
        limiter=RateLimiter(0, 0),
        seen_skus=set(),
    )

    assert "https://www.chewy.com/chewy-peanut-butter-filled-dog-treat/dp/1819711" in fetched
    assert not any(u.endswith("/dp/1819710") for u in fetched)
    assert "1819710" in {v.sku for v in variants}     # sku stays the partNumber
