from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .research_market_data import last_pct_change, load_fred_series, percentile_rank

VIX_SERIES = "VIXCLS"
VIX_3M_SERIES = "VXVCLS"


def _latest(series: pd.Series) -> float:
    clean = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    return float(clean.iloc[-1]) if not clean.empty else np.nan


def classify_volatility_snapshot(vix: pd.Series, vix_3m: pd.Series) -> dict[str, Any]:
    spot = _latest(vix)
    three_month = _latest(vix_3m)
    if not np.isfinite(spot):
        return {"regime": "N/V", "stress": "N/V", "curve": "N/V", "momentum": "N/V", "vix": np.nan, "vix_3m": np.nan, "as_of": None}
    common = pd.concat([pd.Series(vix, name="vix"), pd.Series(vix_3m, name="vix3m")], axis=1).dropna()
    ratio = float(spot / three_month) if np.isfinite(three_month) and three_month != 0 else np.nan
    rank = percentile_rank(pd.Series(vix).dropna().tail(756))
    change_5d = last_pct_change(vix, 5)
    change_20d = last_pct_change(vix, 20)
    curve = "BACKWARDATION" if np.isfinite(ratio) and ratio >= 1.0 else "CONTANGO" if np.isfinite(ratio) and ratio <= 0.95 else "FLAT / MIXED"
    momentum = "RISING" if np.isfinite(change_5d) and change_5d >= 0.10 else "FALLING" if np.isfinite(change_5d) and change_5d <= -0.10 else "STABLE"
    stress_votes = 0
    relief_votes = 0
    if np.isfinite(rank):
        if rank >= 80:
            stress_votes += 1
        elif rank <= 50:
            relief_votes += 1
    if curve == "BACKWARDATION":
        stress_votes += 1
    elif curve == "CONTANGO":
        relief_votes += 1
    if momentum == "RISING":
        stress_votes += 1
    elif momentum == "FALLING":
        relief_votes += 1
    if stress_votes >= 2:
        regime, stress = "RISK-OFF", "ELEVATED"
    elif relief_votes >= 2:
        regime, stress = "RISK-ON", "LOW"
    else:
        regime, stress = "MIXED", "NORMAL"
    as_of = pd.Timestamp(common.index.max()) if not common.empty else pd.Timestamp(pd.Series(vix).dropna().index.max())
    return {
        "regime": regime,
        "stress": stress,
        "curve": curve,
        "momentum": momentum,
        "vix": spot,
        "vix_3m": three_month,
        "curve_ratio": ratio,
        "vix_percentile": rank,
        "change_5d": change_5d,
        "change_20d": change_20d,
        "as_of": as_of,
    }


def build_volatility_regime() -> dict[str, Any]:
    return classify_volatility_snapshot(load_fred_series(VIX_SERIES), load_fred_series(VIX_3M_SERIES))
