"""
Parser tests. Listing-page cases use a trimmed copy of the Oct 2026 Chewy layout
(chirp product cards, ?page=N pagination), as seen via scripts/dump_page.py.
"""
from chewy_scraper.scraper.parsers import parse_page_urls, parse_product_urls

CATEGORY_URL = "https://www.chewy.com/b/bones-1542"

AD_HREF = (
    "https://www.chewy.com/api/event/p/sar/click?adsOrigin=aspen1&amp;id=abc"
    "&amp;productIds=4251918&amp;pos=1"
    "&amp;redirect=https://www.chewy.com/brutus-barnaby-100-usa-beef-high/dp/4251918"
)

LISTING_HTML = f"""
<html><body>
<header><nav><ul><li><a href="/chewy-egift-card/dp/226306">Gift card</a></li></ul></nav></header>
<div data-testid="plp-product-card" class="chirp-product-card">
  <div class="chirp-product-card__content"><a href="{AD_HREF}">Sponsored bone</a></div>
</div>
<div data-testid="plp-product-card" class="chirp-product-card">
  <div class="chirp-product-card__content">
    <a href="https://www.chewy.com/jack-pup-large-roasted-beef-knuckle/dp/551934?sku=1">Knuckle</a>
  </div>
</div>
<div data-testid="plp-product-card" class="chirp-product-card">
  <a href="/jack-pup-large-roasted-beef-knuckle/dp/551934">Knuckle again</a>
</div>
<div data-testid="plp-product-card"><a href="/b/bones-1542">no product link</a></div>
<div class="chirp-product-card"><a href="/not-in-grid/dp/999">Carousel item</a></div>
<nav>
  <a href="/b/bones-1542?page=2">2</a>
  <a href="/b/bones-1542?page=3">3</a>
  <a href="/b/bones-1542?page=7">7</a>
  <a href="/b/antlers-1541?page=40">other category</a>
</nav>
</body></html>
"""


def test_product_urls_from_cards_only():
    assert parse_product_urls(LISTING_HTML) == [
        "https://www.chewy.com/brutus-barnaby-100-usa-beef-high/dp/4251918",
        "https://www.chewy.com/jack-pup-large-roasted-beef-knuckle/dp/551934",
    ]


def test_page_urls_use_highest_page_of_this_category():
    assert parse_page_urls(LISTING_HTML, CATEGORY_URL) == [
        f"{CATEGORY_URL}?page={i}" for i in range(2, 8)
    ]


def test_single_page_category_has_no_extra_pages():
    assert parse_page_urls("<html><body></body></html>", CATEGORY_URL) == []


def test_review_keyword_chips_are_not_variants():
    from chewy_scraper.scraper.parsers import _parse_options
    from bs4 import BeautifulSoup

    html = """
    <input class="kib-chip-choice__control" value="smell" aria-label="smell">
    <input class="kib-chip-choice__control" value="for dogs" aria-label="for dogs">
    """
    assert _parse_options(BeautifulSoup(html, "lxml")) == []


# ── Product page (Oct 2026 layout: data in __NEXT_DATA__ Apollo state) ─────

from pathlib import Path

from chewy_scraper.pipeline.normalizer import parse_nutrition
from chewy_scraper.scraper.parsers import parse_product_page

PDP_HTML = (Path(__file__).parent / "fixtures" / "pdp_next_data.html").read_text()


def test_product_core_fields_from_next_data():
    p = parse_product_page(PDP_HTML)
    assert p is not None
    assert p.sku == "1819678"
    assert p.brand_name == "Chewy Made"
    assert p.item_name.startswith("Peanut Butter Flavored Filled Bone")
    assert p.item_name.endswith("1 count")
    assert p.price_str == "$6.99"
    assert p.image_url.endswith("_AC_SS1800_V1_.jpg")


def test_product_details_from_info_groups():
    p = parse_product_page(PDP_HTML)
    assert p.ingredients_text.startswith("Beef Bone, Chicken Meal")
    assert p.feeding_instructions.startswith("This product is intended")
    assert parse_nutrition(p.nutrition) == {
        "protein_pct": 18.0, "fat_pct": 3.5, "fiber_pct": 2.0, "moisture_pct": 22.0,
    }


def test_variants_are_every_published_item():
    p = parse_product_page(PDP_HTML)
    by_sku = {o.sku: o.label for o in p.options}
    assert len(by_sku) == 9
    assert by_sku["1819678"] == "Peanut Butter, 1 count"
    assert by_sku["1819710"] == "Cheese & Bacon, 5 count"
    assert by_sku["2195470"] == "Peanut Butter, 3 count bundle"
