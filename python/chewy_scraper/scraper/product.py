"""
Product-level scraping: fetch a product page, enumerate all variants,
fetch each variant URL, and return normalised data ready for DB insertion.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from chewy_scraper.config import CategoryConfig, ScrapingConfig
from chewy_scraper.pipeline.normalizer import (
    NormalisedVariant,
    detect_allergens,
    parse_count,
    parse_nutrition,
    parse_price_cents,
    parse_size,
    price_per_each_cents,
)
from chewy_scraper.scraper.browser import fetch_page_html
from chewy_scraper.scraper.parsers import parse_product_page
from chewy_scraper.utils.rate_limiter import RateLimiter
from chewy_scraper.utils.retry import ChewyNotFoundError, with_retry

logger = logging.getLogger(__name__)

BASE_URL = "https://www.chewy.com"


async def scrape_product_variants(
    product_url: str,
    category: CategoryConfig,
    all_allergens: dict[str, list[str]],   # {profile_name: [allergen, ...]}
    config: ScrapingConfig,
    limiter: RateLimiter,
    seen_skus: set[str],
) -> list[NormalisedVariant]:
    """
    Scrape all variants of a single product.

    - Fetches the product page to discover available option SKUs
    - Fetches each unique SKU variant URL
    - Returns a list of NormalisedVariant (one per unique SKU)

    `seen_skus` is shared across all products in a run to prevent
    processing the same SKU via multiple category paths.
    """
    await limiter.wait()
    try:
        base_html = await with_retry(
            lambda: fetch_page_html(product_url, config),
            max_attempts=config.retry_max_attempts,
            backoff_base=config.retry_backoff_base,
        )
    except ChewyNotFoundError:
        logger.warning("404 for product: %s", product_url)
        return []

    parsed = parse_product_page(base_html)
    if parsed is None:
        logger.warning("Could not parse product page: %s", product_url)
        return []

    # If no options found, treat the base page as the single variant
    if not parsed.options:
        return await _scrape_single_variant(
            url=product_url,
            base_parsed=parsed,
            category=category,
            all_allergens=all_allergens,
            config=config,
            limiter=limiter,
            seen_skus=seen_skus,
            sku_override=None,
        )

    results: list[NormalisedVariant] = []
    for option in parsed.options:
        if option.sku in seen_skus:
            continue
        seen_skus.add(option.sku)

        variant_url = f"{product_url.rstrip('/')}/{option.sku}"
        await limiter.wait()
        try:
            variant_html = await with_retry(
                lambda: fetch_page_html(variant_url, config),
                max_attempts=config.retry_max_attempts,
                backoff_base=config.retry_backoff_base,
            )
        except ChewyNotFoundError:
            logger.warning("404 for variant: %s", variant_url)
            continue

        variant_parsed = parse_product_page(variant_html)
        if variant_parsed is None:
            logger.warning("Could not parse variant page: %s", variant_url)
            continue

        normalised = _normalise(
            sku=option.sku,
            option_label=option.label,
            parsed=variant_parsed,
            category=category,
            all_allergens=all_allergens,
        )
        results.append(normalised)

    return results


async def _scrape_single_variant(
    url: str,
    base_parsed,
    category: CategoryConfig,
    all_allergens: dict[str, list[str]],
    config: ScrapingConfig,
    limiter: RateLimiter,
    seen_skus: set[str],
    sku_override: str | None,
) -> list[NormalisedVariant]:
    # Derive a pseudo-SKU from the URL if not available
    from urllib.parse import urlparse
    path_parts = urlparse(url).path.rstrip("/").split("/")
    sku = sku_override or path_parts[-1]

    if sku in seen_skus:
        return []
    seen_skus.add(sku)

    normalised = _normalise(
        sku=sku,
        option_label=None,
        parsed=base_parsed,
        category=category,
        all_allergens=all_allergens,
    )
    return [normalised]


def _normalise(
    sku: str,
    option_label: str | None,
    parsed,
    category: CategoryConfig,
    all_allergens: dict[str, list[str]],
) -> NormalisedVariant:
    # Combine option label and item name for size/count extraction
    search_text = " ".join(filter(None, [option_label, parsed.item_name]))
    size_value, size_unit = parse_size(search_text)
    count_value = parse_count(search_text)

    price_c = parse_price_cents(parsed.price_str)
    ppe = price_per_each_cents(price_c, count_value)

    nutrition: dict[str, float | None] = {}
    if category.want_nutrition:
        nutrition = parse_nutrition(parsed.nutrition)

    # Allergen detection: use ingredients from the product page.
    # Merge allergens from all profiles that apply to this category.
    all_relevant_allergens = [
        allergen
        for profile_name in category.allergen_profiles
        for allergen in all_allergens.get(profile_name, [])
    ]
    allergen_hits = detect_allergens(parsed.ingredients_text, all_relevant_allergens)

    return NormalisedVariant(
        sku=sku,
        brand_name=parsed.brand_name,
        item_name=parsed.item_name,
        image_url=parsed.image_url,
        option_label=option_label,
        size_value=size_value,
        size_unit=size_unit,
        count_value=count_value,
        price_cents=price_c,
        price_per_each_cents=ppe,
        currency="USD",
        protein_pct=nutrition.get("protein_pct"),
        fat_pct=nutrition.get("fat_pct"),
        fiber_pct=nutrition.get("fiber_pct"),
        moisture_pct=nutrition.get("moisture_pct"),
        feeding_instructions=parsed.feeding_instructions if category.want_feeding else None,
        ingredients_text=parsed.ingredients_text,
        allergen_hits=allergen_hits,
    )
