"""
HTML parsing utilities for Chewy.com product and category pages.

All selectors target the current Chewy site design (data-testid attributes,
kib-* class names). Product-page selectors date from the Selenium POC;
listing-page selectors were re-verified in Oct 2026 with
scripts/dump_page.py. Chewy changes
class names periodically so re-verify selectors after major site redesigns.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.chewy.com"
_DP_PATH = re.compile(r"/dp/\d+")

# ── Selectors ──────────────────────────────────────────────────────────────
# Isolated here so they can be updated without touching logic.

SEL_PRODUCT_CARD = {"data-testid": "plp-product-card"}   # verified 2026-10 (chirp redesign)
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
    sku: str | None = None        # part number of the item this page shows


# ── Category / listing page ────────────────────────────────────────────────

def parse_product_urls(html: str) -> list[str]:
    """Extract product URLs from a category listing page."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    for card in soup.find_all(attrs=SEL_PRODUCT_CARD):
        anchor = card.find("a", href=_DP_PATH)
        if not anchor:
            continue
        url = _product_url(anchor["href"])
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _product_url(href: str) -> str | None:
    """
    Normalise a card link to a clean absolute product URL.

    Sponsored cards link through an ad-click tracker whose `redirect` query
    parameter holds the real product URL; those are unwrapped, not skipped,
    because they are genuine products listed in the category.
    """
    if "redirect=" in href:
        target = parse_qs(urlsplit(href).query).get("redirect", [""])[0]
        if not _DP_PATH.search(target):
            return None
        href = target
    parts = urlsplit(urljoin(BASE_URL, href))
    if not _DP_PATH.search(parts.path):
        return None
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def parse_page_urls(html: str, base_category_url: str) -> list[str]:
    """
    Return URLs for pages 2..N of a category listing.
    Page 1 is the base URL already loaded; this returns the rest.

    Pagination links look like /b/bones-1542?page=7. The control may elide
    middle pages, so N is the highest page number linked from this category.
    """
    soup = BeautifulSoup(html, "lxml")
    base = urlsplit(base_category_url)
    num_pages = 1
    for anchor in soup.find_all("a", href=True):
        parts = urlsplit(urljoin(BASE_URL, anchor["href"]))
        if parts.path.rstrip("/") != base.path.rstrip("/"):
            continue
        page = parse_qs(parts.query).get("page", [""])[0]
        if page.isdigit():
            num_pages = max(num_pages, int(page))

    page_base = f"{base.scheme}://{base.netloc}{base.path}"
    return [f"{page_base}?page={i}" for i in range(2, num_pages + 1)]


# ── Product page ───────────────────────────────────────────────────────────

def parse_product_page(html: str) -> ParsedProductPage | None:
    """
    Parse a product page. Returns None if the page doesn't look like a valid
    product (e.g. 404 landing page).
    """
    soup = BeautifulSoup(html, "lxml")

    from_json = _parse_next_data(soup)
    if from_json is not None:
        return from_json

    # Legacy HTML fallback (pre-2026 layout).
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


# ── Product page: embedded Next.js / Apollo data ───────────────────────────
#
# Since the 2026 redesign every product page embeds its data as JSON in
# <script id="__NEXT_DATA__">, at props.pageProps.__APOLLO_STATE__: a flat
# Apollo cache of "Product:<id>", "Item:<id>" (one per variant/SKU) and
# "AttributeValue:{...}" entries linked by {"__ref": key}. ROOT_QUERY's
# item({"id": "<partNumber>"}) points at the item the page is showing; only
# that item carries ingredients / guaranteed analysis / feeding (infoGroups).
# This is far more stable than CSS class names, which change every redesign.

def _parse_next_data(soup: BeautifulSoup) -> ParsedProductPage | None:
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return None
    try:
        state = json.loads(script.string)["props"]["pageProps"]["__APOLLO_STATE__"]
    except (ValueError, KeyError, TypeError):
        return None

    root = state.get("ROOT_QUERY", {})
    item = _deref(state, _first_value(root, "item("))
    product = _deref(state, _first_value(root, "product("))
    if not item or not product:
        return None

    brand_name = product.get("manufacturerName")
    item_name = item.get("name") or product.get("name")
    if brand_name and item_name and item_name.startswith(brand_name):
        item_name = item_name[len(brand_name):].strip()

    sections = {
        section.get("usage"): (section.get("content") or {}).get("content")
        for group in item.get("infoGroups") or []
        for section in group.get("sections") or []
    }

    options: list[ParsedVariantOption] = []
    variants = [_deref(state, ref) for ref in _first_value(product, "items(") or []]
    if len(variants) > 1:
        for variant in variants:
            if not variant or not variant.get("partNumber") or variant.get("isPublished") is False:
                continue
            options.append(ParsedVariantOption(
                sku=variant["partNumber"],
                label=_variant_label(state, variant),
            ))

    return ParsedProductPage(
        brand_name=brand_name,
        item_name=item_name or None,
        image_url=_largest_image(item.get("fullImage")),
        price_str=item.get("advertisedPrice"),
        options=options,
        ingredients_text=sections.get("INGREDIENTS"),
        nutrition=_parse_markdown_table(sections.get("GUARANTEED_ANALYSIS")),
        feeding_instructions=sections.get("FEEDING_INSTRUCTIONS"),
        sku=item.get("partNumber"),
    )


def _first_value(obj: dict, key_prefix: str):
    """Apollo keys embed query args, e.g. 'items({"includeEnsemble":true})'."""
    return next((v for k, v in obj.items() if k.startswith(key_prefix)), None)


def _deref(state: dict, ref) -> dict | None:
    if isinstance(ref, dict) and "__ref" in ref:
        return state.get(ref["__ref"])
    return ref if isinstance(ref, dict) else None


def _variant_label(state: dict, variant: dict) -> str:
    """Defining attributes joined, e.g. 'Peanut Butter, 3 count bundle'."""
    values = [
        (_deref(state, ref) or {}).get("value")
        for ref in _first_value(variant, "attributeValues(") or []
    ]
    return ", ".join(v for v in values if v) or variant.get("name", "")


def _largest_image(image: dict | None) -> str | None:
    """fullImage holds url(...) keys per size; pick the largest square."""
    if not image:
        return None
    best: tuple[int, str] | None = None
    for key, url in image.items():
        m = re.search(r'"(?:square|maxWidth)":(\d+)', key)
        if m and isinstance(url, str) and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), url)
    return best[1] if best else None


def _parse_markdown_table(markdown: str | None) -> dict[str, str]:
    """
    '|Crude Protein(Min)|18.00%|' rows -> {"crude protein(min)": "18.00%"}.
    Header and separator rows are skipped.
    """
    result: dict[str, str] = {}
    for line in (markdown or "").splitlines():
        cells = [c.strip() for c in line.strip().strip(":").strip("|").split("|")]
        if len(cells) < 2 or not cells[1] or set(cells[1]) <= set("-: "):
            continue
        result[cells[0].lower()] = cells[1]
    return result


# ── Product page: legacy HTML helpers ──────────────────────────────────────

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
        if _is_sku(sku) and sku not in seen_skus:
            seen_skus.add(sku)
            options.append(ParsedVariantOption(sku=sku, label=label))

    # Dropdown-style options (only if no chips found)
    if not options:
        for opt in soup.find_all(attrs=SEL_DROPDOWN_OPTION):
            sku = opt.get("value", "").strip()
            label = opt.get("aria-label") or opt.get_text(strip=True)
            if _is_sku(sku) and sku not in seen_skus:
                seen_skus.add(sku)
                options.append(ParsedVariantOption(sku=sku, label=label))

    return options


def _is_sku(value: str) -> bool:
    """
    SKUs are numeric. Since the 2026 redesign the old chip class is also used
    for review-keyword filters ("smell", "texture"), which must not be
    mistaken for variants and fetched as /dp/<id>/smell.
    """
    return value.isdigit()


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
