"""
Normalise raw scraped data into clean, typed values ready for DB insertion.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal


@dataclass
class NormalisedVariant:
    sku: str
    brand_name: str | None
    item_name: str | None
    image_url: str | None
    option_label: str | None
    size_value: float | None
    size_unit: str | None
    count_value: int | None
    price_cents: int | None
    price_per_each_cents: int | None
    currency: str
    protein_pct: float | None
    fat_pct: float | None
    fiber_pct: float | None
    moisture_pct: float | None
    feeding_instructions: str | None
    ingredients_text: str | None
    allergen_hits: dict[str, bool] = field(default_factory=dict)


# ── Price ──────────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r"[\$£€]?\s*([\d,]+\.?\d*)")


def parse_price_cents(price_str: str | None) -> int | None:
    """Parse a price string like '$24.99' or '2.58' into integer cents."""
    if not price_str:
        return None
    m = _PRICE_RE.search(price_str.replace(",", ""))
    if not m:
        return None
    try:
        return int(Decimal(m.group(1)) * 100)
    except Exception:
        return None


def price_per_each_cents(price_cents: int | None, count: int | None) -> int | None:
    """Calculate unit price using floor rounding (matches Java behaviour)."""
    if price_cents is None or not count or count <= 0:
        return price_cents
    result = Decimal(price_cents) / Decimal(count)
    return int(result.to_integral_value(rounding=ROUND_FLOOR))


# ── Size ───────────────────────────────────────────────────────────────────

_SIZE_RE = re.compile(
    r"(\d+\.?\d*)\s*-?\s*(oz|lb|lbs|g|kg|ml|fl\.?\s*oz|pound|ounce)",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "g": "g",
    "kg": "kg",
    "ml": "ml",
    "fl oz": "fl oz", "fl. oz": "fl oz",
}


def parse_size(text: str | None) -> tuple[float | None, str | None]:
    """
    Extract (value, unit) from a string like '2.5 oz', '1-lb', '400g'.
    Returns (None, None) if no match.
    """
    if not text:
        return None, None
    m = _SIZE_RE.search(text)
    if not m:
        return None, None
    value = float(m.group(1))
    raw_unit = m.group(2).lower().replace(".", "").strip()
    unit = _UNIT_MAP.get(raw_unit, raw_unit)
    return value, unit


# ── Count ──────────────────────────────────────────────────────────────────

_COUNT_RE = re.compile(
    r"(\d+)\s*(?:count|ct|pack|packs|piece|pieces|tabs?|capsules?)",
    re.IGNORECASE,
)
_CASE_RE = re.compile(r"case\s+of\s+(\d+)", re.IGNORECASE)


def parse_count(text: str | None, count_standard: str | None = None) -> int | None:
    """
    Extract a count integer from option label, product name, or count_standard.
    Tries count_standard (from API) first as it's the cleanest source.
    """
    if count_standard:
        try:
            return int(count_standard)
        except ValueError:
            pass

    if not text:
        return None

    # "case of N" pattern
    m = _CASE_RE.search(text)
    if m:
        return int(m.group(1))

    m = _COUNT_RE.search(text)
    if m:
        return int(m.group(1))

    return None


# ── Nutrition ──────────────────────────────────────────────────────────────

_PCT_RE = re.compile(r"([\d.]+)\s*%")

# Maps normalised label fragments to output field names
_NUTRITION_KEYS = {
    "crude protein": "protein_pct",
    "protein": "protein_pct",
    "crude fat": "fat_pct",
    "fat": "fat_pct",
    "crude fiber": "fiber_pct",
    "fiber": "fiber_pct",
    "moisture": "moisture_pct",
}


def parse_nutrition(nutrition_table: dict[str, str]) -> dict[str, float | None]:
    """
    Map the raw nutrition label→value dict from HTML parsing into the four
    standardised fields. Returns a dict with keys protein/fat/fiber/moisture_pct.
    """
    out: dict[str, float | None] = {
        "protein_pct": None,
        "fat_pct": None,
        "fiber_pct": None,
        "moisture_pct": None,
    }
    for raw_label, raw_value in nutrition_table.items():
        for fragment, field_name in _NUTRITION_KEYS.items():
            if fragment in raw_label and out[field_name] is None:
                m = _PCT_RE.search(raw_value)
                if m:
                    out[field_name] = float(m.group(1))
                break
    return out


# ── Allergen detection ─────────────────────────────────────────────────────

def detect_allergens(ingredients_text: str | None, allergens: list[str]) -> dict[str, bool]:
    """
    Case-insensitive substring match for each allergen in ingredients_text.
    Returns {allergen: detected} for every allergen in the list.
    """
    if not ingredients_text:
        return {a: False for a in allergens}
    lower = ingredients_text.lower()
    return {a: a.lower() in lower for a in allergens}
