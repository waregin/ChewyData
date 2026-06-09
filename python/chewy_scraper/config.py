from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class DatabaseConfig(BaseModel):
    url: str
    pool_size: int = 5


class ScrapingConfig(BaseModel):
    concurrency: int = 3
    request_delay_min: float = 2.0
    request_delay_max: float = 6.0
    retry_max_attempts: int = 5
    retry_backoff_base: float = 2.0
    user_agents: list[str]
    proxy_url: str | None = None

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
