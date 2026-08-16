import ast
import unittest
from pathlib import Path
from src.fx_relative_core import CURRENCY_ORDER


class V3442ForexMatrixHotfixTests(unittest.TestCase):
    def test_forex_universe(self):
        self.assertEqual(
            tuple(CURRENCY_ORDER),
            ("EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "MXN", "JPY"),
        )
        self.assertNotIn("BRL", CURRENCY_ORDER)
        self.assertNotIn("ZAR", CURRENCY_ORDER)

    def test_confirmation_denominator_is_four(self):
        source = Path("pages/forex_matrix.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('f"▲ BULLISH {confirmations}/4"', source)
        self.assertIn('f"▼ BÄRISCH {confirmations}/4"', source)
        self.assertNotIn('{confirmations}/3', source)

    def test_runtime_filters_profiles(self):
        source = Path("src/fx_relative.py").read_text(encoding="utf-8")
        self.assertIn('profiles["symbol"].isin(CURRENCY_ORDER)', source)

    def test_brl_zar_still_in_main_universe(self):
        source = Path("src/markets.py").read_text(encoding="utf-8")
        self.assertIn('"symbol": "BRL"', source)
        self.assertIn('"symbol": "ZAR"', source)


if __name__ == "__main__":
    unittest.main()
