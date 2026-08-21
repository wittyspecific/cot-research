from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .research_market_data import last_change, load_fred_series, percentile_rank

HY_OAS_SERIES = "BAMLH0A0HYM2"
IG_OAS_SERIES = "BAMLC0A0CM"


def _latest(series: pd.Series) -> float:
    clean = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    return float(clean.iloc[-1]) if not clean.empty else np.nan


def classify_credit_snapshot(hy: pd.Series, ig: pd.Series) -> dict[str, Any]:
    hy = pd.to_numeric(pd.Series(hy), errors="coerce").dropna()
    ig = pd.to_numeric(pd.Series(ig), errors="coerce").dropna()
    if hy.empty:
        return {"regime": "N/V", "direction": "N/V", "hy_oas": np.nan, "ig_oas": np.nan, "as_of": None}
    joined = pd.concat([hy.rename("hy"), ig.rename("ig")], axis=1).dropna()
    hy_now = _latest(hy)
    ig_now = _latest(ig)
    hy_rank = percentile_rank(hy.tail(756))
    hy_change_20d = last_change(hy, 20)
    differential = joined["hy"] - joined["ig"] if not joined.empty else pd.Series(dtype=float)
    diff_now = _latest(differential)
    diff_rank = percentile_rank(differential.tail(756))
    stress_votes = 0
    calm_votes = 0
    if np.isfinite(hy_rank):
        if hy_rank >= 80:
            stress_votes += 1
        elif hy_rank <= 55:
            calm_votes += 1
    if np.isfinite(diff_rank):
        if diff_rank >= 80:
            stress_votes += 1
        elif diff_rank <= 55:
            calm_votes += 1
    if np.isfinite(hy_change_20d):
        if hy_change_20d > 0.20:
            stress_votes += 1
        elif hy_change_20d < -0.10:
            calm_votes += 1
    regime = "STRESS" if stress_votes >= 2 else "CALM" if calm_votes >= 2 else "MIXED"
    direction = "WIDENING" if np.isfinite(hy_change_20d) and hy_change_20d > 0 else "TIGHTENING" if np.isfinite(hy_change_20d) and hy_change_20d < 0 else "STABLE"
    as_of = pd.Timestamp(joined.index.max()) if not joined.empty else pd.Timestamp(hy.index.max())
    return {
        "regime": regime,
        "direction": direction,
        "hy_oas": hy_now,
        "ig_oas": ig_now,
        "hy_ig_gap": diff_now,
        "hy_percentile": hy_rank,
        "gap_percentile": diff_rank,
        "hy_change_20d": hy_change_20d,
        "as_of": as_of,
    }


def build_credit_stress() -> dict[str, Any]:
    return classify_credit_snapshot(load_fred_series(HY_OAS_SERIES), load_fred_series(IG_OAS_SERIES))
