"""
CLI entry point for the Chewy scraper.

Usage:
  chewy-scraper [OPTIONS]
  python -m chewy_scraper [OPTIONS]

Designed to be called by cron or GitHub Actions; exits with:
  0 = success
  1 = completed with errors
  2 = fatal error (config invalid, DB unreachable, etc.)
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from chewy_scraper.config import load_config
from chewy_scraper.db import get_session, init_db
from chewy_scraper.pipeline.writer import (
    finish_run,
    start_run,
    upsert_category,
    upsert_pet_profiles,
    upsert_product,
    upsert_variant,
    write_variant_snapshots,
)
from chewy_scraper.scraper.browser import fetch_page_html, start_browser, stop_browser
from chewy_scraper.scraper.category import collect_product_urls
from chewy_scraper.scraper.product import scrape_product_variants
from chewy_scraper.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", "config_path", default="config.yaml",
              show_default=True, help="Path to config.yaml")
@click.option("--categories", default=None,
              help="Comma-separated category names to run (default: all)")
@click.option("--dry-run", is_flag=True, default=False,
              help="Scrape but do not write to database")
@click.option("--log-level", default="INFO", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False))
def cli(config_path: str, categories: str | None, dry_run: bool, log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        cfg = load_config(config_path)
    except Exception as e:
        click.echo(f"Failed to load config: {e}", err=True)
        sys.exit(2)

    selected = None
    if categories:
        selected = {c.strip() for c in categories.split(",")}

    active_categories = [
        c for c in cfg.categories
        if selected is None or c.name in selected
    ]
    if not active_categories:
        click.echo("No matching categories found.", err=True)
        sys.exit(2)

    if not dry_run:
        try:
            init_db(cfg.database)
        except Exception as e:
            click.echo(f"Failed to initialise database: {e}", err=True)
            sys.exit(2)

    exit_code = asyncio.run(_run(cfg, active_categories, dry_run))
    sys.exit(exit_code)


async def _run(cfg, active_categories, dry_run: bool) -> int:
    all_allergens = {
        p.name: p.allergens for p in cfg.pet_profiles
    }

    await start_browser(cfg.scraping)
    limiter = RateLimiter(cfg.scraping.request_delay_min, cfg.scraping.request_delay_max)
    errors = 0
    run_id: int | None = None

    try:
        if not dry_run:
            async with get_session() as session:
                profile_id_map = await upsert_pet_profiles(
                    session,
                    [{"name": p.name, "allergens": p.allergens} for p in cfg.pet_profiles],
                )
                run_id = await start_run(session)

        for category in active_categories:
            logger.info("=== Starting category: %s ===", category.name)
            try:
                product_urls = await collect_product_urls(category, cfg.scraping, limiter)
            except Exception as e:
                logger.error("Failed to collect URLs for category '%s': %s", category.name, e)
                errors += 1
                continue

            if not dry_run:
                profile_ids = []
                async with get_session() as session:
                    pid_map = {p.name: p.id for p in
                               (await session.execute(__import__("sqlalchemy", fromlist=["select"]).select(
                                   __import__("chewy_scraper.models", fromlist=["PetProfile"]).PetProfile
                               ))).scalars()}
                    profile_ids = [
                        pid_map[name]
                        for name in category.allergen_profiles
                        if name in pid_map
                    ]
                    cat_id = await upsert_category(
                        session,
                        name=category.name,
                        url=category.url,
                        size_matters=category.size_matters,
                        want_nutrition=category.want_nutrition,
                        want_feeding=category.want_feeding,
                        allergen_profile_ids=profile_ids,
                    )

            seen_skus: set[str] = set()
            for i, product_url in enumerate(product_urls, 1):
                logger.debug("[%d/%d] %s", i, len(product_urls), product_url)
                try:
                    variants = await scrape_product_variants(
                        product_url=product_url,
                        category=category,
                        all_allergens=all_allergens,
                        config=cfg.scraping,
                        limiter=limiter,
                        seen_skus=seen_skus,
                    )
                except Exception as e:
                    logger.error("Error scraping %s: %s", product_url, e)
                    errors += 1
                    continue

                if dry_run:
                    for v in variants:
                        logger.info("[DRY RUN] sku=%s brand=%s price_cents=%s allergens=%s",
                                    v.sku, v.brand_name, v.price_cents,
                                    {k: det for k, det in v.allergen_hits.items() if det})
                    continue

                now = datetime.now(tz=timezone.utc)
                try:
                    async with get_session() as session:
                        product_id = await upsert_product(
                            session, cat_id, product_url,
                            brand_name=variants[0].brand_name if variants else None,
                            item_name=variants[0].item_name if variants else None,
                            image_url=variants[0].image_url if variants else None,
                            now=now,
                        )
                        for variant in variants:
                            variant_id = await upsert_variant(session, product_id, variant, now)
                            profile_id_map_for_variant = {
                                name: pid
                                for name, pid in profile_id_map.items()
                                if name in category.allergen_profiles
                            }
                            await write_variant_snapshots(
                                session, run_id, variant_id, variant,
                                profile_id_map_for_variant, now,
                            )
                except Exception as e:
                    logger.error("DB write failed for %s: %s", product_url, e)
                    errors += 1

                if i % 50 == 0:
                    logger.info("Progress: %d/%d products in '%s'",
                                i, len(product_urls), category.name)

            logger.info("=== Finished category: %s ===", category.name)

        if not dry_run and run_id is not None:
            status = "complete" if errors == 0 else "complete_with_errors"
            async with get_session() as session:
                await finish_run(session, run_id, status)

    except Exception as e:
        logger.exception("Fatal error: %s", e)
        if not dry_run and run_id is not None:
            async with get_session() as session:
                await finish_run(session, run_id, "failed")
        return 2
    finally:
        await stop_browser()

    logger.info("Run complete. Errors: %d", errors)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    cli()
