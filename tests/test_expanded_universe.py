import unittest
from pathlib import Path

from src.markets import CLASSIC_MARKETS


class ExpandedUniverseTests(unittest.TestCase):
    def _by_symbol(self):
        return {
            market["symbol"]: (asset_class, market)
            for asset_class, markets in CLASSIC_MARKETS.items()
            for market in markets
        }

    def test_universe_contains_prior_expansion_and_new_markets(self):
        total = sum(len(markets) for markets in CLASSIC_MARKETS.values())
        self.assertEqual(total, 51)

    def test_new_markets_exist(self):
        markets = self._by_symbol()
        for symbol in ("BTC", "ETH", "MXN", "USD"):
            self.assertIn(symbol, markets)

    def test_new_market_tickers(self):
        markets = self._by_symbol()
        self.assertEqual(markets["BTC"][1]["ticker"], "BTC=F")
        self.assertEqual(markets["ETH"][1]["ticker"], "ETH=F")
        self.assertEqual(markets["MXN"][1]["ticker"], "6M=F")
        self.assertEqual(markets["USD"][1]["ticker"], "DX-Y.NYB")

    def test_crypto_has_own_asset_class(self):
        markets = self._by_symbol()
        self.assertEqual(markets["BTC"][0], "Cryptocurrencies")
        self.assertEqual(markets["ETH"][0], "Cryptocurrencies")

    def test_crypto_tff_routing_is_configured(self):
        source = Path("src/cftc_reports.py").read_text(encoding="utf-8")
        self.assertIn('"Cryptocurrencies"', source)
        self.assertIn('"Rates"', source)
        self.assertIn('"Volatility"', source)

    def test_mxn_outight_fx_guard_is_configured(self):
        for filename in ("src/cftc.py", "src/cftc_reports.py"):
            source = Path(filename).read_text(encoding="utf-8")
            self.assertIn('"MXN"', source)


if __name__ == "__main__":
    unittest.main()
