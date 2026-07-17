from pathlib import Path

import pytest

from chewy_scraper.config import load_config

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def test_loads_without_error():
    cfg = load_config(CONFIG_PATH)
    assert cfg is not None


def test_sixteen_categories():
    cfg = load_config(CONFIG_PATH)
    assert len(cfg.categories) == 16


def test_cat_food_has_allergen_profile():
    cfg = load_config(CONFIG_PATH)
    cat_food = [c for c in cfg.categories if "cat" in c.name.lower() and "food" in c.name.lower()]
    assert len(cat_food) == 5
    for category in cat_food:
        assert "cat" in category.allergen_profiles, (
            f"Category '{category.name}' should have allergen_profiles=['cat']"
        )


def test_dog_treats_have_no_allergen_profiles():
    cfg = load_config(CONFIG_PATH)
    treat_names = [
        "Dental Chews", "Bully Sticks", "Bones", "Rawhide", "Antlers",
        "Himalayan Chews", "Natural Chews", "Rawhide Alternatives", "Hard Chews",
        "Pill Treats",
    ]
    treats = [c for c in cfg.categories if c.name in treat_names]
    assert len(treats) == 10
    for t in treats:
        assert t.allergen_profiles == [], f"Treat '{t.name}' should have no allergen profiles"


def test_cat_profile_has_sixteen_allergens():
    cfg = load_config(CONFIG_PATH)
    cat = cfg.pet_profile("cat")
    assert cat is not None
    assert len(cat.allergens) == 16


def test_mulberry_not_misspelled():
    cfg = load_config(CONFIG_PATH)
    cat = cfg.pet_profile("cat")
    assert "mulberry" in cat.allergens
    assert "mulberr" not in cat.allergens


def test_delay_max_gte_min():
    cfg = load_config(CONFIG_PATH)
    assert cfg.scraping.request_delay_max >= cfg.scraping.request_delay_min


def test_headed_by_default():
    # Headless is the biggest Akamai detection signal — must default off.
    cfg = load_config(CONFIG_PATH)
    assert cfg.scraping.headless is False


def test_persistent_profile_configured():
    cfg = load_config(CONFIG_PATH)
    assert cfg.scraping.profile_dir
    # Must not be the literal Guest profile (Guest forgets cookies).
    assert "guest" not in cfg.scraping.profile_dir.lower()


def test_gentle_pacing():
    # Serial, slow pacing is the whole point of the free anti-ban approach.
    cfg = load_config(CONFIG_PATH)
    assert cfg.scraping.concurrency == 1
    assert cfg.scraping.request_delay_min >= 3.0
