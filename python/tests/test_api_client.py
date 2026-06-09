import json
from pathlib import Path

import pytest

from chewy_scraper.scraper.api_client import extract_catalog_id_from_url, parse_api_response

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


@pytest.fixture
def api_data():
    with open(FIXTURE, encoding="latin-1") as f:
        return json.load(f)


class TestParseApiResponse:
    def test_returns_variants(self, api_data):
        variants = parse_api_response(api_data)
        assert len(variants) > 0

    def test_sku_populated(self, api_data):
        variants = parse_api_response(api_data)
        assert all(v.sku for v in variants)

    def test_no_duplicate_skus(self, api_data):
        variants = parse_api_response(api_data)
        skus = [v.sku for v in variants]
        assert len(skus) == len(set(skus))

    def test_price_present(self, api_data):
        variants = parse_api_response(api_data)
        # At least one variant should have a price
        assert any(v.price_str is not None for v in variants)

    def test_ingredients_present(self, api_data):
        variants = parse_api_response(api_data)
        # The fixture is a dental chew — ingredients should be populated
        variants_with_ingredients = [v for v in variants if v.ingredients]
        assert len(variants_with_ingredients) > 0

    def test_brand_present(self, api_data):
        variants = parse_api_response(api_data)
        assert any(v.brand for v in variants)

    def test_image_url_normalised(self, api_data):
        variants = parse_api_response(api_data)
        for v in variants:
            if v.image_url:
                assert v.image_url.startswith("https://")


class TestExtractCatalogId:
    def test_standard_url(self):
        url = "https://www.chewy.com/ziwi-peak-air-dried/dp/232835"
        assert extract_catalog_id_from_url(url) == "232835"

    def test_url_with_trailing_slash(self):
        url = "https://www.chewy.com/brand-product/dp/99999/"
        assert extract_catalog_id_from_url(url) == "99999"

    def test_url_without_dp(self):
        url = "https://www.chewy.com/b/dental-chews-1463"
        assert extract_catalog_id_from_url(url) is None
