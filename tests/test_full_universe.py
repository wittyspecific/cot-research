import unittest
from pathlib import Path

from src.markets import CLASSIC_MARKETS


EXPECTED_CODES = {
    "OJ": "040701",
    "VIX": "1170E1",
    "ZT": "042601",
    "ZF": "044601",
    "ZN": "043602",
    "ZB": "020601",
    "UB": "020604",
    "KE": "001612",
    "MWE": "001626",
    "ZR": "039601",
    "LBR": "058644",
    "BRL": "102741",
    "ZAR": "122741",
    "BZ": "06765T",
    "RS": "135731",
}


class FullUniverseTests(unittest.TestCase):
    def markets(self):
        return {
            market["symbol"]: (asset_class, market)
            for asset_class, rows in CLASSIC_MARKETS.items()
            for market in rows
        }

    def test_total_is_51(self):
        self.assertEqual(
            sum(len(rows) for rows in CLASSIC_MARKETS.values()),
            51,
        )

    def test_all_15_new_markets_have_official_codes(self):
        markets = self.markets()
        for symbol, code in EXPECTED_CODES.items():
            self.assertIn(symbol, markets)
            self.assertEqual(markets[symbol][1]["cftc_code"], code)

    def test_rates_and_vix_classes(self):
        markets = self.markets()
        for symbol in ("ZT", "ZF", "ZN", "ZB", "UB"):
            self.assertEqual(markets[symbol][0], "Rates")
        self.assertEqual(markets["VIX"][0], "Volatility")
        self.assertEqual(markets["LBR"][0], "Forest Products")

    def test_verified_price_tickers(self):
        markets = self.markets()
        expected = {
            "OJ": "OJ=F",
            "VIX": "^VIX",
            "ZT": "ZT=F",
            "ZF": "ZF=F",
            "ZN": "ZN=F",
            "ZB": "ZB=F",
            "UB": "UB=F",
            "KE": "KE=F",
            "ZR": "ZR=F",
            "LBR": "LBR=F",
            "BRL": "6L=F",
            "ZAR": "6Z=F",
            "BZ": "BZ=F",
        }
        for symbol, ticker in expected.items():
            self.assertEqual(markets[symbol][1]["ticker"], ticker)

    def test_unverified_price_feeds_are_not_faked(self):
        markets = self.markets()
        self.assertEqual(markets["MWE"][1]["ticker"], "")
        self.assertEqual(markets["RS"][1]["ticker"], "")

    def test_brent_last_day_exception_is_scoped(self):
        markets = self.markets()
        self.assertEqual(
            markets["BZ"][1]["allow_excluded_terms"],
            ["LAST DAY"],
        )

    def test_resolvers_use_contract_code_fast_path(self):
        for filename in ("src/cftc.py", "src/cftc_reports.py"):
            source = Path(filename).read_text(encoding="utf-8")
            self.assertIn("target_contract_code", source)
            self.assertIn(
                "row_contract_code == target_contract_code",
                source,
            )
            self.assertIn("allowed_excluded_terms", source)

    def test_modern_routing(self):
        source = Path("src/cftc_reports.py").read_text(encoding="utf-8")
        self.assertIn('"Rates"', source)
        self.assertIn('"Volatility"', source)
        self.assertIn('"Forest Products"', source)


if __name__ == "__main__":
    unittest.main()
