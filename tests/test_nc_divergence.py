import unittest

import numpy as np
import pandas as pd

from src.nc_divergence import (
    build_divergence_history,
    exact_week_lag,
    robust_z_from_prior_history,
    redundancy_metrics,
)


class NCDivergenceTests(unittest.TestCase):
    def test_exact_week_lag_does_not_stretch_missing_week(self):
        dates = pd.Series(pd.to_datetime([
            "2026-01-06",
            "2026-01-13",
            "2026-01-20",
            # Jan 27 intentionally missing
            "2026-02-03",
        ]))
        values = pd.Series([1.0, 2.0, 3.0, 5.0])
        lag = exact_week_lag(dates, values, 1)
        self.assertTrue(np.isnan(lag.iloc[-1]))  # Jan 27 missing

    def test_robust_z_excludes_current_observation_from_reference(self):
        s = pd.Series([0.0, 0.0, 1.0, 1.0, 100.0])
        z = robust_z_from_prior_history(s, history_weeks=4)
        # If the current 100 entered its own reference distribution, the result
        # would be materially compressed. The prior-only IQR is finite and tiny.
        self.assertTrue(np.isfinite(z.iloc[-1]))
        self.assertGreater(z.iloc[-1], 50)

    def test_bullish_divergence_on_synthetic_opposite_path(self):
        # 220 complete Tuesday observations provide enough prior history.
        dates = pd.date_range("2021-01-05", periods=220, freq="W-TUE")
        base_price = np.linspace(100.0, 110.0, len(dates))
        base_net_oi = np.linspace(-0.10, -0.05, len(dates))

        # Historical variation so IQRs are non-zero.
        base_price = base_price * (1 + 0.01 * np.sin(np.arange(len(dates)) / 3.0))
        base_net_oi = base_net_oi + 0.005 * np.sin(np.arange(len(dates)) / 4.0)

        # Last 9 weeks: price descends, speculative net/OI rises.
        base_price[-9:] = np.linspace(112.0, 95.0, 9)
        base_net_oi[-9:] = np.linspace(-0.08, 0.02, 9)

        oi = np.full(len(dates), 100_000.0)
        net = base_net_oi * oi
        long = 60_000.0 + net / 2.0
        short = 60_000.0 - net / 2.0

        frame = pd.DataFrame({
            "report_date": dates,
            "cot_price": base_price,
            "cot_price_date": dates,
            "cot_price_alignment_ok": True,
            "open_interest_all": oi,
            "spec_long": long,
            "spec_short": short,
        })
        hist = build_divergence_history(
            frame,
            long_col="spec_long",
            short_col="spec_short",
        )
        last = hist.iloc[-1]
        self.assertLess(last["z_price"], -1.0)
        self.assertGreater(last["z_flow"], 1.0)
        self.assertLess(last["rho"], 0.0)
        self.assertEqual(int(last["direction"]), 1)

    def test_legacy_redundancy_identity_is_detected(self):
        dates = pd.date_range("2020-01-07", periods=120, freq="W-TUE")
        t = np.arange(len(dates), dtype=float)
        comm_net = 1000.0 * np.sin(t / 7.0)
        nr_net = 250.0 * np.cos(t / 5.0)
        nc_net = -(comm_net + nr_net)
        oi = np.full(len(dates), 100_000.0)

        def legs(net):
            return 50_000.0 + net / 2.0, 50_000.0 - net / 2.0

        c_long, c_short = legs(comm_net)
        n_long, n_short = legs(nc_net)
        r_long, r_short = legs(nr_net)
        frame = pd.DataFrame({
            "report_date": dates,
            "open_interest_all": oi,
            "commercial_long": c_long,
            "commercial_short": c_short,
            "noncommercial_long": n_long,
            "noncommercial_short": n_short,
            "retail_long": r_long,
            "retail_short": r_short,
        })
        m = redundancy_metrics(
            frame,
            hedger_key="commercial",
            speculative_key="noncommercial",
            nonreportable_key="retail",
            flow_weeks=4,
        )
        self.assertLess(m["pearson_raw"], -0.85)
        self.assertGreater(m["nonreportable_difference_r2"], 0.99)


    def test_invalid_price_alignment_suppresses_signal(self):
        dates = pd.date_range("2021-01-05", periods=220, freq="W-TUE")
        price = 100 + np.sin(np.arange(len(dates)) / 5.0)
        oi = np.full(len(dates), 100_000.0)
        long = 55_000 + 500 * np.sin(np.arange(len(dates)) / 4.0)
        short = 45_000 - 500 * np.sin(np.arange(len(dates)) / 4.0)
        ok = np.ones(len(dates), dtype=bool)
        ok[-1] = False
        frame = pd.DataFrame({
            "report_date": dates,
            "cot_price": price,
            "cot_price_date": dates,
            "cot_price_alignment_ok": ok,
            "open_interest_all": oi,
            "spec_long": long,
            "spec_short": short,
        })
        hist = build_divergence_history(frame, "spec_long", "spec_short")
        self.assertEqual(hist.iloc[-1]["status"], "PRICE ALIGNMENT INVALID")
        self.assertEqual(int(hist.iloc[-1]["direction"]), 0)


if __name__ == "__main__":
    unittest.main()
