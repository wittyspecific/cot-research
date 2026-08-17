import ast
import unittest
from pathlib import Path

import pandas as pd


class NCPercentileConfirmationRegressionTests(unittest.TestCase):
    def test_watchlist_replaces_old_fourth_condition_with_cross_group_pipeline(self):
        source = Path("pages/watchlist.py").read_text(encoding="utf-8")
        self.assertIn("Cross-Group Shift", source)
        self.assertIn("Asset Manager + Leveraged Funds", source)
        self.assertIn("Producer/Merchant + Managed Money", source)
        self.assertIn("Nonreportable", source)
        self.assertNotIn('"4/4 Voll"', source)

    def test_watchlist_engine_exposes_nc_percentile(self):
        source = Path("src/watchlist.py").read_text(encoding="utf-8")
        self.assertIn('"noncommercial_net_percentile": float(', source)

    def test_forex_runtime_passes_nc_percentile(self):
        source = Path("src/fx_relative.py").read_text(encoding="utf-8")
        self.assertIn('noncommercial_net_percentile=latest[', source)

    def test_forex_ui_displays_nc_percentile(self):
        source = Path("pages/forex_matrix.py").read_text(encoding="utf-8")
        self.assertIn('"Non-Commercial": value_text(', source)

    def test_commercial_high_nc_low_is_bullish_confirmation(self):
        from src.fx_relative_core import currency_cot_profile
        row = currency_cot_profile(
            symbol="CAD",
            market_name="Canadian Dollar",
            report_date=pd.Timestamp("2026-08-11"),
            commercial_index=95,
            commercial_net_percentile=95,
            noncommercial_net_percentile=5,
            retail_net_percentile=10,
            cycle_phase="RELEASE", cycle_direction=1, extreme_direction=1, cycle_state="BULLISH RELEASE",
        )
        self.assertEqual(row["confirmations"], 4)
        self.assertEqual(row["signed_strength"], 4)
        self.assertTrue(row["noncommercial_ok"])

    def test_commercial_low_nc_high_is_bearish_confirmation(self):
        from src.fx_relative_core import currency_cot_profile
        row = currency_cot_profile(
            symbol="CHF",
            market_name="Swiss Franc",
            report_date=pd.Timestamp("2026-08-11"),
            commercial_index=5,
            commercial_net_percentile=5,
            noncommercial_net_percentile=95,
            retail_net_percentile=90,
            cycle_phase="RELEASE", cycle_direction=-1, extreme_direction=-1, cycle_state="BEARISH RELEASE",
        )
        self.assertEqual(row["confirmations"], 4)
        self.assertEqual(row["signed_strength"], -4)
        self.assertTrue(row["noncommercial_ok"])


if __name__ == "__main__":
    unittest.main()
