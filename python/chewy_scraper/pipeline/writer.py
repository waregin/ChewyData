"""
Write normalised scrape results to PostgreSQL.
Each variant is written as a transaction; a failure on one variant does not
roll back others (partial runs are preserved and resumable).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from chewy_scraper.models import (
    AllergenDetection,
    Category,
    CategoryAllergenProfile,
    NutritionSnapshot,
    PetAllergen,
    PetProfile,
    PriceSnapshot,
    Product,
    ProductVariant,
    ScrapeRun,
)
from chewy_scraper.pipeline.normalizer import NormalisedVariant

logger = logging.getLogger(__name__)


async def upsert_pet_profiles(session: AsyncSession, profiles: list[dict]) -> dict[str, int]:
    """
    Ensure pet_profiles and pet_allergens rows exist for every configured profile.
    Returns {profile_name: profile_id}.
    """
    id_map: dict[str, int] = {}
    for profile in profiles:
        name = profile["name"]
        allergens = profile["allergens"]

        result = await session.execute(select(PetProfile).where(PetProfile.name == name))
        row = result.scalar_one_or_none()
        if row is None:
            row = PetProfile(name=name)
            session.add(row)
            await session.flush()

        id_map[name] = row.id

        # Sync allergen list
        existing = await session.execute(
            select(PetAllergen).where(PetAllergen.profile_id == row.id)
        )
        existing_allergens = {a.allergen for a in existing.scalars()}
        for allergen in allergens:
            if allergen not in existing_allergens:
                session.add(PetAllergen(profile_id=row.id, allergen=allergen))

    return id_map


async def upsert_category(
    session: AsyncSession,
    name: str,
    url: str,
    size_matters: bool,
    want_nutrition: bool,
    want_feeding: bool,
    allergen_profile_ids: list[int],
) -> int:
    """Ensure category row exists; return its id."""
    result = await session.execute(select(Category).where(Category.name == name))
    row = result.scalar_one_or_none()
    if row is None:
        row = Category(
            name=name,
            url=url,
            size_matters=size_matters,
            want_nutrition=want_nutrition,
            want_feeding=want_feeding,
        )
        session.add(row)
        await session.flush()

    # Sync allergen profile links
    existing = await session.execute(
        select(CategoryAllergenProfile).where(CategoryAllergenProfile.category_id == row.id)
    )
    existing_ids = {link.profile_id for link in existing.scalars()}
    for pid in allergen_profile_ids:
        if pid not in existing_ids:
            session.add(CategoryAllergenProfile(category_id=row.id, profile_id=pid))

    return row.id


async def upsert_product(
    session: AsyncSession,
    category_id: int,
    url: str,
    brand_name: str | None,
    item_name: str | None,
    image_url: str | None,
    now: datetime,
) -> int:
    """Upsert product row; update last_seen_at and metadata on revisit."""
    result = await session.execute(select(Product).where(Product.url == url))
    row = result.scalar_one_or_none()
    if row is None:
        row = Product(
            category_id=category_id,
            url=url,
            brand_name=brand_name,
            item_name=item_name,
            image_url=image_url,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(row)
    else:
        row.last_seen_at = now
        row.brand_name = brand_name or row.brand_name
        row.item_name = item_name or row.item_name
        row.image_url = image_url or row.image_url
    await session.flush()
    return row.id


async def upsert_variant(
    session: AsyncSession,
    product_id: int,
    variant: NormalisedVariant,
    now: datetime,
) -> int:
    """Upsert variant row; update last_seen_at on revisit."""
    result = await session.execute(
        select(ProductVariant).where(ProductVariant.sku == variant.sku)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ProductVariant(
            product_id=product_id,
            sku=variant.sku,
            option_label=variant.option_label,
            size_value=variant.size_value,
            size_unit=variant.size_unit,
            count_value=variant.count_value,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(row)
    else:
        row.last_seen_at = now
        row.option_label = variant.option_label or row.option_label
    await session.flush()
    return row.id


async def write_variant_snapshots(
    session: AsyncSession,
    run_id: int,
    variant_id: int,
    variant: NormalisedVariant,
    profile_id_map: dict[str, int],
    now: datetime,
) -> None:
    """Write price snapshot, optional nutrition snapshot, and allergen detections."""
    session.add(PriceSnapshot(
        run_id=run_id,
        variant_id=variant_id,
        scraped_at=now,
        price_cents=variant.price_cents,
        price_per_each_cents=variant.price_per_each_cents,
        currency=variant.currency,
    ))

    if any(v is not None for v in [
        variant.protein_pct, variant.fat_pct, variant.fiber_pct, variant.moisture_pct
    ]):
        session.add(NutritionSnapshot(
            run_id=run_id,
            variant_id=variant_id,
            scraped_at=now,
            protein_pct=variant.protein_pct,
            fat_pct=variant.fat_pct,
            fiber_pct=variant.fiber_pct,
            moisture_pct=variant.moisture_pct,
            feeding_instructions=variant.feeding_instructions,
        ))

    # allergen_hits is keyed by allergen string, but we need profile_id.
    # The caller populates allergen_hits as {allergen: detected} for all
    # allergens across all profiles. We store one row per allergen, attaching
    # it to the profile it belongs to via profile_id_map.
    for profile_name, profile_id in profile_id_map.items():
        profile_allergens = {
            allergen
            for allergen, _detected in variant.allergen_hits.items()
        }
        for allergen, detected in variant.allergen_hits.items():
            session.add(AllergenDetection(
                run_id=run_id,
                variant_id=variant_id,
                profile_id=profile_id,
                scraped_at=now,
                allergen=allergen,
                detected=detected,
            ))


async def start_run(session: AsyncSession) -> int:
    run = ScrapeRun(started_at=datetime.now(tz=timezone.utc), status="running")
    session.add(run)
    await session.flush()
    return run.id


async def finish_run(session: AsyncSession, run_id: int, status: str = "complete") -> None:
    result = await session.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))
    run = result.scalar_one()
    run.status = status
    run.finished_at = datetime.now(tz=timezone.utc)
