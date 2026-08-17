import unittest

import pandas as pd

from src.fx_relative_core import (
    build_all_fx_pairs,
    classify_20y_40d_seasonality,
    currency_cot_profile,
    pair_bias_from_strength,
)


class FXRelativeTests(unittest.TestCase):
    def test_cad_3_chf_minus_3_is_strong_bullish(self):
        result = pair_bias_from_strength(3, -3)
        self.assertEqual(result["edge"], 6)
        self.assertEqual(result["strength_label"], "STARK BULLISH")
        self.assertEqual(result["trade_bias"], "LONG-BIAS")


    def test_four_vs_minus_four_is_strong_bullish(self):
        result = pair_bias_from_strength(4, -4)
        self.assertEqual(result["edge"], 8)
        self.assertEqual(result["strength_label"], "STARK BULLISH")
        self.assertEqual(result["trade_bias"], "LONG-BIAS")

    def test_one_vs_minus_one_is_light_bullish(self):
        result = pair_bias_from_strength(1, -1)
        self.assertEqual(result["edge"], 2)
        self.assertEqual(result["strength_label"], "LEICHT BULLISH")

    def test_bullish_currency_4_of_4(self):
        row = currency_cot_profile(
            symbol="CAD",
            market_name="Canadian Dollar",
            report_date=pd.Timestamp("2026-08-11"),
            commercial_index=95,
            commercial_net_percentile=91,
            noncommercial_net_percentile=7,
            retail_net_percentile=8,
            cycle_phase="RELEASE",
            cycle_direction=1,
            extreme_direction=1,
            cycle_state="BULLISH RELEASE",
        )
        self.assertEqual(row["signed_strength"], 4)
        self.assertTrue(row["noncommercial_ok"])


    def test_full_hedge_extreme_is_state_not_signal(self):
        row = currency_cot_profile(
            symbol="CAD", market_name="Canadian Dollar", report_date=pd.Timestamp("2026-08-11"),
            commercial_index=100, commercial_net_percentile=95, noncommercial_net_percentile=5, retail_net_percentile=10,
            cycle_phase="EXTREME", cycle_direction=0, extreme_direction=1, cycle_state="FULL HEDGE · PERSISTENCE",
        )
        self.assertEqual(row["signed_strength"], 0)
        self.assertEqual(row["bias"], "NEUTRAL")
        self.assertEqual(row["state_label"], "FULL HEDGE")
        self.assertEqual(row["signal_label"], "WAITING FOR RELEASE")

    def test_9_currencies_make_36_pairs(self):
        symbols = [
            "EUR", "GBP", "AUD", "NZD", "USD",
            "CAD", "CHF", "MXN", "JPY",
        ]
        strengths = [4, 3, 2, 1, 0, -1, -2, -3, -4]
        rows = []
        for symbol, strength in zip(symbols, strengths):
            rows.append(
                {
                    "symbol": symbol,
                    "bias": (
                        "BULLISH" if strength > 0
                        else "BÄRISCH" if strength < 0
                        else "NEUTRAL"
                    ),
                    "direction": 1 if strength > 0 else -1 if strength < 0 else 0,
                    "confirmations": abs(strength),
                    "signed_strength": strength,
                }
            )
        pairs = build_all_fx_pairs(pd.DataFrame(rows))
        self.assertEqual(len(pairs), 36)
        self.assertIn("CADCHF", set(pairs["pair"]))
        self.assertIn("AUDCAD", set(pairs["pair"]))

    def test_20y_40d_supports_long(self):
        result = classify_20y_40d_seasonality(
            pair_direction=1,
            sample_size=20,
            positive_years=14,
            positive_rate=0.70,
            base_rate=0.53,
            median_return=0.021,
        )
        self.assertEqual(result["support"], "UNTERSTÜTZT")
        self.assertTrue(result["supports"])
        self.assertEqual(result["seasonal_label"], "BULLISH")

    def test_20y_40d_opposes_short(self):
        result = classify_20y_40d_seasonality(
            pair_direction=-1,
            sample_size=20,
            positive_years=14,
            positive_rate=0.70,
            base_rate=0.53,
            median_return=0.021,
        )
        self.assertEqual(result["support"], "GEGENLÄUFIG")
        self.assertFalse(result["supports"])

    def test_too_few_years_is_na(self):
        result = classify_20y_40d_seasonality(
            pair_direction=1,
            sample_size=6,
            positive_years=5,
            positive_rate=0.83,
            base_rate=0.50,
            median_return=0.03,
        )
        self.assertEqual(result["support"], "N/V")


if __name__ == "__main__":
    unittest.main()
