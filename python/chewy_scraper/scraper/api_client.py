"""
Client for Chewy's internal product attribute/SKU API.

The endpoint and response format were discovered by capturing network traffic
on a Chewy product page (see scripts/spike_api.py for the discovery tool).
The data.json fixture in tests/fixtures/ is a sample response.

Endpoint pattern (to be confirmed via spike):
  GET https://www.chewy.com/api/2.0/catalog/category/{catalogEntryId}/facets
       ?facetType=catalog&availableOnly=true&...

Each item in the response list represents an attribute group (e.g. "Count",
"Size") with attributeValues containing per-SKU data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ApiVariant:
    """All per-SKU data extracted from a single attributeValue entry."""
    sku: str                          # partNumber
    name: str
    brand: str | None
    option_label: str | None          # e.g. "1 count"
    price_str: str | None             # e.g. "2.58"
    currency: str
    image_url: str | None
    weight: float | None
    weight_unit: str | None
    size_standard: str | None         # e.g. "2.8-oz"
    count_standard: str | None        # e.g. "1"
    pet_type: str | None
    breed_size: str | None
    ingredients: str | None
    in_stock: bool


def parse_api_response(data: list[dict]) -> list[ApiVariant]:
    """
    Parse the raw API JSON list into a flat list of ApiVariant objects.
    Deduplicates by SKU — if the same partNumber appears in multiple
    attribute groups, the first occurrence wins.
    """
    seen: set[str] = set()
    variants: list[ApiVariant] = []

    for attr_group in data:
        for av in attr_group.get("attributeValues", []):
            sku_obj = av.get("sku") or {}
            sku_dto = av.get("skuDto") or {}
            part_number: str = (
                sku_dto.get("partNumber")
                or sku_obj.get("partNumber")
                or ""
            )
            if not part_number or part_number in seen:
                continue
            seen.add(part_number)

            descriptive = {
                d["identifier"]: d.get("value", "")
                for d in sku_dto.get("descriptiveAttributes", [])
                if "identifier" in d
            }

            pricing = sku_dto.get("pricing") or {}
            weight_info = sku_dto.get("weight") or {}
            full_image = sku_dto.get("fullImage") or sku_obj.get("fullImage")

            variants.append(ApiVariant(
                sku=part_number,
                name=sku_dto.get("name") or sku_obj.get("name") or "",
                brand=sku_dto.get("brand") or sku_obj.get("manufacturer"),
                option_label=av.get("value"),
                price_str=(
                    pricing.get("offerPrice")
                    or pricing.get("advertisedPrice")
                ),
                currency=pricing.get("currency", "USD"),
                image_url=_normalise_image_url(full_image),
                weight=weight_info.get("weight"),
                weight_unit=weight_info.get("weightMeasure"),
                size_standard=descriptive.get("SizeStandard"),
                count_standard=descriptive.get("CountStandard"),
                pet_type=descriptive.get("PetType"),
                breed_size=descriptive.get("BreedSize"),
                ingredients=descriptive.get("Ingredients"),
                in_stock=sku_dto.get("isBuyable", True) and sku_obj.get("inStock", True),
            ))

    return variants


def _normalise_image_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    return url


# ── Endpoint URL helpers ───────────────────────────────────────────────────

# Updated once the spike confirms the real endpoint.
# Set to None to disable API fetching and fall back to HTML-only mode.
API_ENDPOINT_TEMPLATE: str | None = None


def build_api_url(catalog_entry_id: str) -> str | None:
    """Return the API URL for a given product catalog entry ID, or None if
    the endpoint hasn't been confirmed yet."""
    if API_ENDPOINT_TEMPLATE is None:
        return None
    return API_ENDPOINT_TEMPLATE.format(id=catalog_entry_id)


def extract_catalog_id_from_url(product_url: str) -> str | None:
    """
    Chewy product URLs end with a numeric ID, e.g.:
      https://www.chewy.com/brand-name-product/dp/12345
    This extracts '12345'.
    """
    m = re.search(r"/dp/(\d+)", product_url)
    return m.group(1) if m else None
