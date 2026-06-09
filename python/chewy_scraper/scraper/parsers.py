"""
HTML parsing utilities for Chewy.com product and category pages.

All selectors target the current Chewy site design (data-testid attributes,
kib-* class names). Confirmed working as of the Selenium POC; Chewy changes
class names periodically so re-verify selectors after major site redesigns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.chewy.com"

# ── Selectors ──────────────────────────────────────────────────────────────
# Isolated here so they can be updated without touching logic.

SEL_PRODUCT_CARD = "kib-product-card__content"
SEL_PAGINATION_ITEM = "kib-pagination-new__list-item"
SEL_PRODUCT_TITLE = {"data-testid": "product-title"}
SEL_MANUFACTURE_NAME = {"data-testid": "manufacture-name"}
SEL_PRODUCT_HEADING = {"data-testid": "product-title-heading"}
SEL_PRICE = {"data-testid": "advertised-price"}
SEL_IMAGE_CLASS_FRAGMENT = "mainCarouselImage"
SEL_CHIP_OPTION = "kib-chip-choice__control"
SEL_DROPDOWN_OPTION = {"data-testid": "dropdown-radio-input"}
SEL_INGREDIENTS = "INGREDIENTS-section"
SEL_NUTRITION = "GUARANTEED_ANALYSIS-section"
SEL_FEEDING = "FEEDING_INSTRUCTIONS-section"


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class ParsedVariantOption:
    sku: str
    label: str


@dataclass
class ParsedProductPage:
    brand_name: str | None
    item_name: str | None
    image_url: str | None
    price_str: str | None         # raw string e.g. "$24.99"
    options: list[ParsedVariantOption] = field(default_factory=list)
    ingredients_text: str | None = None
    nutrition: dict[str, str] = field(default_factory=dict)
    feeding_instructions: str | None = None


# ── Category / listing page ────────────────────────────────────────────────

def parse_product_urls(html: str) -> list[str]:
    """Extract product URLs from a category listing page."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    for card in soup.find_all(class_=SEL_PRODUCT_CARD):
        anchor = card.find("a", href=True)
        if not anchor:
            continue
        href: str = anchor["href"]
        # Skip ad/tracking links
        if "ms.tagdelivery" in href:
            continue
        # Normalise to absolute URL
        if href.startswith("/"):
            href = BASE_URL + href
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def parse_page_urls(html: str, base_category_url: str) -> list[str]:
    """
    Return URLs for pages 2..N of a category listing.
    Page 1 is the base URL already loaded; this returns the rest.
    """
    soup = BeautifulSoup(html, "lxml")
    items = soup.find_all(class_=SEL_PAGINATION_ITEM)
    if len(items) < 2:
        return []

    try:
        num_pages = int(items[-1].get_text(strip=True))
    except (ValueError, IndexError):
        return []

    if num_pages <= 1:
        return []

    # Derive page-2 URL from the last pagination link, then replace page number
    last_anchor = items[-1].find("a", href=True)
    if not last_anchor:
        return []
    last_href: str = last_anchor["href"]
    if last_href.startswith("/"):
        last_href = BASE_URL + last_href

    urls: list[str] = []
    for i in range(2, num_pages + 1):
        url = re.sub(r"p\d+", f"p{i}", last_href)
        if url not in urls:
            urls.append(url)
    return urls


# ── Product page ───────────────────────────────────────────────────────────

def parse_product_page(html: str) -> ParsedProductPage | None:
    """
    Parse a product page. Returns None if the page doesn't look like a valid
    product (e.g. 404 landing page).
    """
    soup = BeautifulSoup(html, "lxml")

    title_block = soup.find(attrs=SEL_PRODUCT_TITLE)
    if title_block is None:
        return None

    brand_name = _parse_brand(title_block)
    item_name = _parse_item_name(title_block, brand_name)
    image_url = _parse_image(soup)
    price_str = _parse_price(soup)
    options = _parse_options(soup)
    ingredients_text = _parse_text_section(soup, SEL_INGREDIENTS)
    nutrition = _parse_nutrition_table(soup)
    feeding_instructions = _parse_text_section(soup, SEL_FEEDING)

    return ParsedProductPage(
        brand_name=brand_name,
        item_name=item_name,
        image_url=image_url,
        price_str=price_str,
        options=options,
        ingredients_text=ingredients_text,
        nutrition=nutrition,
        feeding_instructions=feeding_instructions,
    )


def _parse_brand(title_block: Tag) -> str | None:
    mfr = title_block.find(attrs=SEL_MANUFACTURE_NAME)
    if not mfr:
        return None
    anchor = mfr.find("a")
    return anchor.get_text(strip=True) if anchor else mfr.get_text(strip=True) or None


def _parse_item_name(title_block: Tag, brand_name: str | None) -> str | None:
    heading = title_block.find(attrs=SEL_PRODUCT_HEADING)
    if not heading:
        return None
    name = heading.get_text(strip=True)
    if brand_name and name.startswith(brand_name):
        name = name[len(brand_name):].strip()
    return name or None


def _parse_image(soup: BeautifulSoup) -> str | None:
    img = soup.find("img", class_=lambda c: c and SEL_IMAGE_CLASS_FRAGMENT in " ".join(c))
    if img:
        src = img.get("src") or img.get("data-src")
        if src:
            return src if src.startswith("http") else "https:" + src
    return None


def _parse_price(soup: BeautifulSoup) -> str | None:
    el = soup.find(attrs=SEL_PRICE)
    if not el:
        return None
    text = el.get_text(separator=" ", strip=True)
    # Strip "Chewy Price" label that sometimes appears
    text = text.replace("Chewy Price", "").strip()
    return text or None


def _parse_options(soup: BeautifulSoup) -> list[ParsedVariantOption]:
    """
    Detect and parse product variant options.
    Chewy uses two UI patterns: chip buttons or dropdown selects.
    Each option carries a value that encodes the SKU.
    """
    options: list[ParsedVariantOption] = []
    seen_skus: set[str] = set()

    # Chip-style options
    for chip in soup.find_all(class_=SEL_CHIP_OPTION):
        sku = chip.get("value", "").strip()
        label = chip.get("aria-label") or chip.get_text(strip=True)
        if sku and sku not in seen_skus:
            seen_skus.add(sku)
            options.append(ParsedVariantOption(sku=sku, label=label))

    # Dropdown-style options (only if no chips found)
    if not options:
        for opt in soup.find_all(attrs=SEL_DROPDOWN_OPTION):
            sku = opt.get("value", "").strip()
            label = opt.get("aria-label") or opt.get_text(strip=True)
            if sku and sku not in seen_skus:
                seen_skus.add(sku)
                options.append(ParsedVariantOption(sku=sku, label=label))

    return options


def _parse_text_section(soup: BeautifulSoup, section_id: str) -> str | None:
    section = soup.find(id=section_id)
    if not section:
        return None
    text = section.get_text(separator=" ", strip=True)
    return text or None


def _parse_nutrition_table(soup: BeautifulSoup) -> dict[str, str]:
    """
    Parse the Guaranteed Analysis section. Returns a dict of
    lowercase label -> value string, e.g. {"crude protein": "28.0%"}.
    """
    section = soup.find(id=SEL_NUTRITION)
    if not section:
        return {}

    result: dict[str, str] = {}
    for row in section.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            if label and value:
                result[label] = value
    return result
