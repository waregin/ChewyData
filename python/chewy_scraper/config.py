from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class DatabaseConfig(BaseModel):
    url: str
    pool_size: int = 5


class ScrapingConfig(BaseModel):
    # Concurrency 1 = one page at a time. Gentle by design — Akamai punishes bursts.
    concurrency: int = 1
    request_delay_min: float = 5.0
    request_delay_max: float = 12.0
    retry_max_attempts: int = 4
    retry_backoff_base: float = 5.0
    user_agents: list[str]
    proxy_url: str | None = None

    # ── Anti-bot / stealth (Chewy uses Akamai Bot Manager) ────────────────
    headless: bool = False          # headed evades far better; set True only if it works
    stealth: bool = True            # inject fingerprint evasions before page scripts
    warmup_url: str = "https://www.chewy.com"  # visit first so Akamai sets cookies
    warmup_pause: float = 4.0       # seconds to let Akamai's sensor JS settle

    # ── Persistent, logged-out scraping profile ───────────────────────────
    # A dedicated Chrome profile dir (NOT your main profile, NOT Guest) that
    # keeps its Akamai cookies between runs so you look like a returning
    # visitor. Created automatically on first run.
    profile_dir: str = ".chrome-profile"
    # Set to "chrome" to drive your REAL installed Chrome (more authentic
    # fingerprint than Playwright's bundled Chromium). Requires Chrome
    # installed. Leave null to use the bundled Chromium.
    browser_channel: str | None = None
    # Safety cap: stop after N products per run. null = no cap. Keeping runs
    # small and infrequent is the best defence against a rate-limit ban.
    max_products_per_run: int | None = None
    # Seconds to wait after a 429 before giving up the run entirely.
    rate_limit_cooldown: float = 300.0

    @field_validator("request_delay_max")
    @classmethod
    def max_gte_min(cls, v: float, info) -> float:
        min_val = info.data.get("request_delay_min", 0)
        if v < min_val:
            raise ValueError("request_delay_max must be >= request_delay_min")
        return v


class PetProfile(BaseModel):
    name: str
    allergens: list[str]


class CategoryConfig(BaseModel):
    name: str
    url: str
    size_matters: bool = False
    want_nutrition: bool = False
    want_feeding: bool = False
    allergen_profiles: list[str] = []


class AppConfig(BaseModel):
    database: DatabaseConfig
    scraping: ScrapingConfig
    pet_profiles: list[PetProfile] = []
    categories: list[CategoryConfig]

    def pet_profile(self, name: str) -> PetProfile | None:
        return next((p for p in self.pet_profiles if p.name == name), None)

    def allergens_for_profile(self, name: str) -> list[str]:
        profile = self.pet_profile(name)
        return profile.allergens if profile else []


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
