import unittest

from src.watchlist_seasonality_core import classify_asset_seasonality


class WatchlistSeasonalityTests(unittest.TestCase):
    def test_bullish_supported(self):
        result = classify_asset_seasonality(
            cot_direction=1,
            sample_size=20,
            positive_years=14,
            positive_rate=0.70,
            base_rate=0.53,
            median_return=0.03,
        )
        self.assertEqual(result["support"], "UNTERSTÜTZT")
        self.assertTrue(result["supports"])
        self.assertEqual(result["sort_rank"], 3)

    def test_bearish_supported(self):
        result = classify_asset_seasonality(
            cot_direction=-1,
            sample_size=20,
            positive_years=7,
            positive_rate=0.35,
            base_rate=0.52,
            median_return=-0.02,
        )
        self.assertEqual(result["support"], "UNTERSTÜTZT")

    def test_opposite_is_contrary(self):
        result = classify_asset_seasonality(
            cot_direction=1,
            sample_size=20,
            positive_years=6,
            positive_rate=0.30,
            base_rate=0.52,
            median_return=-0.02,
        )
        self.assertEqual(result["support"], "GEGENLÄUFIG")

    def test_mixed_is_mixed(self):
        result = classify_asset_seasonality(
            cot_direction=1,
            sample_size=20,
            positive_years=11,
            positive_rate=0.55,
            base_rate=0.52,
            median_return=-0.005,
        )
        self.assertEqual(result["support"], "GEMISCHT")

    def test_too_few_years_is_na(self):
        result = classify_asset_seasonality(
            cot_direction=1,
            sample_size=6,
            positive_years=5,
            positive_rate=0.83,
            base_rate=0.52,
            median_return=0.05,
        )
        self.assertEqual(result["support"], "N/V")
        self.assertEqual(result["sort_rank"], 0)


if __name__ == "__main__":
    unittest.main()
