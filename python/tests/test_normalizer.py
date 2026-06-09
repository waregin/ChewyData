from chewy_scraper.pipeline.normalizer import (
    detect_allergens,
    parse_count,
    parse_nutrition,
    parse_price_cents,
    parse_size,
    price_per_each_cents,
)


class TestParsePrice:
    def test_dollar_sign(self):
        assert parse_price_cents("$24.99") == 2499

    def test_no_dollar_sign(self):
        assert parse_price_cents("2.58") == 258

    def test_chewy_price_label_stripped(self):
        assert parse_price_cents("Chewy Price $14.49") == 1449

    def test_none_input(self):
        assert parse_price_cents(None) is None

    def test_no_price_in_string(self):
        assert parse_price_cents("free") is None

    def test_comma_in_price(self):
        assert parse_price_cents("$1,299.99") == 129999


class TestPricePerEach:
    def test_divides_correctly(self):
        # $12.00 / 10 = $1.20 = 120 cents
        assert price_per_each_cents(1200, 10) == 120

    def test_floor_rounding(self):
        # $10.00 / 3 = $3.333... → floors to 333 cents
        assert price_per_each_cents(1000, 3) == 333

    def test_none_price(self):
        assert price_per_each_cents(None, 5) is None

    def test_none_count(self):
        assert price_per_each_cents(500, None) == 500

    def test_zero_count(self):
        assert price_per_each_cents(500, 0) == 500


class TestParseSize:
    def test_oz(self):
        assert parse_size("3 oz bag") == (3.0, "oz")

    def test_lb(self):
        assert parse_size("5 lb bag") == (5.0, "lb")

    def test_decimal(self):
        assert parse_size("2.5 oz") == (2.5, "oz")

    def test_hyphenated(self):
        assert parse_size("2.8-oz") == (2.8, "oz")

    def test_no_size(self):
        assert parse_size("large breed formula") == (None, None)

    def test_none(self):
        assert parse_size(None) == (None, None)

    def test_lbs_normalised_to_lb(self):
        val, unit = parse_size("10 lbs")
        assert unit == "lb"

    def test_kg(self):
        assert parse_size("1.5kg") == (1.5, "kg")


class TestParseCount:
    def test_count_keyword(self):
        assert parse_count("30 count") == 30

    def test_ct_keyword(self):
        assert parse_count("24 ct") == 24

    def test_case_of(self):
        assert parse_count("case of 12") == 12

    def test_pack(self):
        assert parse_count("6 pack") == 6

    def test_count_standard_wins(self):
        assert parse_count("5 count blah", count_standard="10") == 10

    def test_count_standard_invalid_falls_through(self):
        assert parse_count("5 count", count_standard="abc") == 5

    def test_none(self):
        assert parse_count(None) is None


class TestParseNutrition:
    def test_all_four_fields(self):
        table = {
            "crude protein (min)": "28.0%",
            "crude fat (min)": "15.0%",
            "crude fiber (max)": "4.0%",
            "moisture (max)": "10.0%",
        }
        result = parse_nutrition(table)
        assert result["protein_pct"] == 28.0
        assert result["fat_pct"] == 15.0
        assert result["fiber_pct"] == 4.0
        assert result["moisture_pct"] == 10.0

    def test_missing_fields_are_none(self):
        result = parse_nutrition({"crude protein (min)": "30%"})
        assert result["protein_pct"] == 30.0
        assert result["fat_pct"] is None

    def test_empty_table(self):
        result = parse_nutrition({})
        assert all(v is None for v in result.values())


class TestDetectAllergens:
    ALLERGENS = ["rice", "corn", "wheat", "peanut"]

    def test_detects_present(self):
        text = "Chicken, Rice Flour, Corn Starch, Vitamins"
        result = detect_allergens(text, self.ALLERGENS)
        assert result["rice"] is True
        assert result["corn"] is True
        assert result["wheat"] is False
        assert result["peanut"] is False

    def test_case_insensitive(self):
        result = detect_allergens("WHEAT FLOUR, SALT", self.ALLERGENS)
        assert result["wheat"] is True

    def test_no_ingredients(self):
        result = detect_allergens(None, self.ALLERGENS)
        assert all(v is False for v in result.values())

    def test_empty_allergen_list(self):
        result = detect_allergens("rice, corn, wheat", [])
        assert result == {}

    def test_all_clear(self):
        result = detect_allergens("Chicken, Turkey, Salmon, Vitamins", self.ALLERGENS)
        assert all(v is False for v in result.values())
