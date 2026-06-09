from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ


class Base(DeclarativeBase):
    pass


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    price_snapshots: Mapped[list[PriceSnapshot]] = relationship(back_populates="run")
    nutrition_snapshots: Mapped[list[NutritionSnapshot]] = relationship(back_populates="run")
    allergen_detections: Mapped[list[AllergenDetection]] = relationship(back_populates="run")


class PetProfile(Base):
    __tablename__ = "pet_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    allergens: Mapped[list[PetAllergen]] = relationship(back_populates="profile")
    category_links: Mapped[list[CategoryAllergenProfile]] = relationship(back_populates="profile")


class PetAllergen(Base):
    __tablename__ = "pet_allergens"
    __table_args__ = (UniqueConstraint("profile_id", "allergen"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pet_profiles.id"), nullable=False)
    allergen: Mapped[str] = mapped_column(String(100), nullable=False)

    profile: Mapped[PetProfile] = relationship(back_populates="allergens")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    size_matters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    want_nutrition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    want_feeding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    products: Mapped[list[Product]] = relationship(back_populates="category")
    allergen_profile_links: Mapped[list[CategoryAllergenProfile]] = relationship(back_populates="category")


class CategoryAllergenProfile(Base):
    __tablename__ = "category_allergen_profiles"
    __table_args__ = (UniqueConstraint("category_id", "profile_id"),)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pet_profiles.id"), primary_key=True)

    category: Mapped[Category] = relationship(back_populates="allergen_profile_links")
    profile: Mapped[PetProfile] = relationship(back_populates="category_links")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    option_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    size_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    count_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    product: Mapped[Product] = relationship(back_populates="variants")
    price_snapshots: Mapped[list[PriceSnapshot]] = relationship(back_populates="variant")
    nutrition_snapshots: Mapped[list[NutritionSnapshot]] = relationship(back_populates="variant")
    allergen_detections: Mapped[list[AllergenDetection]] = relationship(back_populates="variant")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_per_each_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="USD")

    run: Mapped[ScrapeRun] = relationship(back_populates="price_snapshots")
    variant: Mapped[ProductVariant] = relationship(back_populates="price_snapshots")


class NutritionSnapshot(Base):
    __tablename__ = "nutrition_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    protein_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fat_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fiber_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    moisture_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    feeding_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[ScrapeRun] = relationship(back_populates="nutrition_snapshots")
    variant: Mapped[ProductVariant] = relationship(back_populates="nutrition_snapshots")


class AllergenDetection(Base):
    __tablename__ = "allergen_detections"
    __table_args__ = (UniqueConstraint("run_id", "variant_id", "profile_id", "allergen"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(ForeignKey("pet_profiles.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    allergen: Mapped[str] = mapped_column(String(100), nullable=False)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)

    run: Mapped[ScrapeRun] = relationship(back_populates="allergen_detections")
    variant: Mapped[ProductVariant] = relationship(back_populates="allergen_detections")
