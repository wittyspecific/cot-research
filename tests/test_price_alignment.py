import sys
import types
import unittest

import pandas as pd

# Keep this unit test runnable even before optional app dependencies are installed.
if "streamlit" not in sys.modules:
    st = types.ModuleType("streamlit")
    class _Cache:
        def __call__(self, *args, **kwargs):
            def deco(fn):
                return fn
            return deco
    st.cache_data = _Cache()
    sys.modules["streamlit"] = st
if "yfinance" not in sys.modules:
    yf = types.ModuleType("yfinance")
    yf.download = lambda *args, **kwargs: pd.DataFrame()
    sys.modules["yfinance"] = yf

from src.prices import align_prices_to_cot, price_alignment_audit


class PriceAlignmentTests(unittest.TestCase):
    def test_last_close_is_never_after_report_and_is_same_week(self):
        cot = pd.DataFrame({
            "report_date": pd.to_datetime(["2026-01-06", "2026-01-13", "2026-01-20"]),
        })
        prices = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 103.0, 104.0]},
            index=pd.to_datetime([
                "2026-01-05",
                "2026-01-06",
                "2026-01-12",
                "2026-01-13",
                "2026-01-20",
            ]),
        )
        out = align_prices_to_cot(cot, prices)
        self.assertTrue(out["cot_price_alignment_ok"].all())
        self.assertTrue((out["cot_price_date"] <= out["report_date"]).all())
        audit = price_alignment_audit(out)
        self.assertEqual(audit["future_prices"], 0)
        self.assertEqual(audit["valid"], 3)

    def test_prior_week_price_is_flagged_instead_of_silently_accepted(self):
        cot = pd.DataFrame({"report_date": pd.to_datetime(["2026-01-13"])})
        prices = pd.DataFrame(
            {"close": [100.0]},
            index=pd.to_datetime(["2026-01-09"]),
        )
        out = align_prices_to_cot(cot, prices)
        self.assertFalse(bool(out.iloc[0]["cot_price_alignment_ok"]))
        self.assertLessEqual(out.iloc[0]["cot_price_date"], out.iloc[0]["report_date"])

    def test_report_dates_are_auditable_by_weekday(self):
        cot = pd.DataFrame({"report_date": pd.to_datetime(["2026-01-06", "2026-01-13"])})
        prices = pd.DataFrame(
            {"close": [100.0, 101.0]},
            index=pd.to_datetime(["2026-01-06", "2026-01-13"]),
        )
        out = align_prices_to_cot(cot, prices)
        audit = price_alignment_audit(out)
        self.assertEqual(audit["report_weekdays"].get("Tuesday"), 2)


if __name__ == "__main__":
    unittest.main()
