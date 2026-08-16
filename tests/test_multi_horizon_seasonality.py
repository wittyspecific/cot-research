import unittest

from src.watchlist_seasonality_core import summarize_multi_horizon
from src.fx_relative_core import summarize_fx_horizons


class MultiHorizonSeasonalityTests(unittest.TestCase):
    def test_all_three_supported_is_stable(self):
        r={20:{"support":"UNTERSTÜTZT","detail":"a"},40:{"support":"UNTERSTÜTZT","detail":"b"},60:{"support":"UNTERSTÜTZT","detail":"c"}}
        s=summarize_multi_horizon(r)
        self.assertEqual(s["overall"],"STABIL UNTERSTÜTZT")
        self.assertEqual(s["compact"],"20✓ · 40✓ · 60✓")
        self.assertEqual(s["overall_rank"],4)

    def test_short_supported_long_opposed_is_mixed(self):
        r={20:{"support":"UNTERSTÜTZT"},40:{"support":"UNTERSTÜTZT"},60:{"support":"GEGENLÄUFIG"}}
        s=summarize_multi_horizon(r)
        self.assertEqual(s["overall"],"GEMISCHT")
        self.assertEqual(s["compact"],"20✓ · 40✓ · 60✕")

    def test_fx_summary(self):
        r={20:{"support":"UNTERSTÜTZT"},40:{"support":"UNTERSTÜTZT"},60:{"support":"UNTERSTÜTZT"}}
        s=summarize_fx_horizons(r)
        self.assertEqual(s["compact"],"20✓ · 40✓ · 60✓")
        self.assertEqual(s["overall_rank"],4)

if __name__=='__main__': unittest.main()
