from __future__ import annotations

from math import sqrt
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .fx_relative import load_currency_usd_values, synthesize_pair_prices
from .yield_cot_fx_returns import _forward_return_after

# V3.19.1 · REGIME-AWARE COT × RATES EVENT STUDY
# IMPORTANT: This module does NOT define or modify COT logic.
# It only reads already-produced COT phases/directions and groups them for research:
# EXTREME -> WATCH, TRANSITION -> EARLY, RELEASE/CONFIRMED -> ACTIVE.

RETURN_HORIZONS = (1, 4, 8)
STAGE_RANK = {"NEUTRAL": 0, "WATCH": 1, "EARLY": 2, "ACTIVE": 3}


def _finite(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if np.isfinite(x) else default


def _sign(value: Any) -> int:
    x = _finite(value, 0.0)
    return 1 if x > 0 else -1 if x < 0 else 0


def cot_phase_to_research_stage(phase: Any) -> str:
    value = str(phase or "NEUTRAL").upper().strip()
    if value in {"RELEASE", "CONFIRMED"}:
        return "ACTIVE"
    if value == "TRANSITION":
        return "EARLY"
    if value == "EXTREME":
        return "WATCH"
    return "NEUTRAL"


def rates_strength(percentile: Any) -> str:
    p = _finite(percentile)
    if not np.isfinite(p):
        return "N/V"
    if p >= 90:
        return "EXTREME"
    if p >= 75:
        return "STRONG"
    return "NORMAL"


def _pair_cot_stage(row: Mapping[str, Any]) -> str:
    pair_dir = _sign(row.get("cot_pair_direction"))
    base_dir = _sign(row.get("base_cot_direction"))
    quote_dir = _sign(row.get("quote_cot_direction"))
    if pair_dir == 0:
        return "NEUTRAL"

    phases = []
    if (pair_dir > 0 and base_dir > 0) or (pair_dir < 0 and base_dir < 0):
        phases.append(row.get("base_cot_phase", "NEUTRAL"))
    if (pair_dir > 0 and quote_dir < 0) or (pair_dir < 0 and quote_dir > 0):
        phases.append(row.get("quote_cot_phase", "NEUTRAL"))
    if not phases:
        return "NEUTRAL"
    stages = [cot_phase_to_research_stage(x) for x in phases]
    return max(stages, key=lambda x: STAGE_RANK.get(x, 0))


def _relationship(cot_direction: int, rates_direction: int) -> str:
    cot = int(np.sign(int(cot_direction or 0)))
    rates = int(np.sign(int(rates_direction or 0)))
    if cot and rates:
        return "ALIGNED" if cot == rates else "CONFLICT"
    if cot:
        return "COT_ONLY"
    if rates:
        return "RATES_ONLY"
    return "NEUTRAL"


def _wilson(wins: int, n: int) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    z = 1.959963984540054
    p = wins / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return max(0.0, center - half), min(1.0, center + half)


def _metrics(subset: pd.DataFrame, direction: pd.Series, horizon: int) -> dict[str, Any]:
    raw = pd.to_numeric(subset[f"return_{horizon}w"], errors="coerce")
    oriented = (raw * direction.astype(float)).dropna()
    oriented = oriented[np.isfinite(oriented)]
    if oriented.empty:
        return {"n": 0, "Hit Rate": np.nan, "CI Low": np.nan, "CI High": np.nan,
                "Median Return": np.nan, "Mean Return": np.nan}
    wins = int((oriented > 0).sum())
    n = int(len(oriented))
    low, high = _wilson(wins, n)
    return {"n": n, "Hit Rate": wins / n, "CI Low": low, "CI High": high,
            "Median Return": float(oriented.median()), "Mean Return": float(oriented.mean())}


def _prepare_weekly(weekly: pd.DataFrame) -> pd.DataFrame:
    required = {
        "pair", "base", "quote", "available_date", "cot_pair_direction",
        "base_cot_direction", "quote_cot_direction", "base_cot_phase", "quote_cot_phase",
        "rates20_delta_bp", "rates20_percentile", "rates5_direction", "rates60_direction",
    }
    missing = sorted(required.difference(weekly.columns))
    if missing:
        raise RuntimeError("V3.19.1 Research-Felder fehlen: " + ", ".join(missing))

    out = weekly.copy().sort_values(["pair", "available_date"]).reset_index(drop=True)
    out["available_date"] = pd.to_datetime(out["available_date"], errors="coerce")
    out["cot_stage"] = out.apply(_pair_cot_stage, axis=1)
    out["rates_strength"] = out["rates20_percentile"].map(rates_strength)
    out["rates20_raw_direction"] = pd.to_numeric(out["rates20_delta_bp"], errors="coerce").map(_sign)
    out["relationship"] = out.apply(
        lambda r: _relationship(int(r["cot_pair_direction"]), int(r["rates20_raw_direction"])), axis=1
    )
    out["confirm5"] = out.apply(
        lambda r: int(int(r.get("rates5_direction", 0) or 0) != 0 and
                      int(r.get("rates5_direction", 0) or 0) == int(r["rates20_raw_direction"])), axis=1
    )
    out["confirm60"] = out.apply(
        lambda r: int(int(r.get("rates60_direction", 0) or 0) != 0 and
                      int(r.get("rates60_direction", 0) or 0) == int(r["rates20_raw_direction"])), axis=1
    )

    starts = pd.Series(False, index=out.index)
    for _, group in out.groupby("pair", sort=False):
        previous_date = None
        previous_state = None
        for idx in group.index:
            r = out.loc[idx]
            date = pd.Timestamp(r["available_date"])
            state = (r["cot_stage"], int(r["cot_pair_direction"]), r["rates_strength"],
                     int(r["rates20_raw_direction"]), r["relationship"], int(r["confirm5"]), int(r["confirm60"]))
            starts.loc[idx] = previous_date is None or (date - previous_date).days > 10 or state != previous_state
            previous_date, previous_state = date, state
    out["event_start"] = starts.astype(bool)
    return out


def _attach_returns(events: pd.DataFrame) -> pd.DataFrame:
    fx = load_currency_usd_values(start="2000-01-01")
    out = events.copy()
    for h in RETURN_HORIZONS:
        out[f"return_{h}w"] = np.nan
    for _, group in out.groupby("pair", sort=False):
        first = group.iloc[0]
        base, quote = str(first["base"]), str(first["quote"])
        if base not in fx or quote not in fx:
            continue
        prices = synthesize_pair_prices(base, quote, dict(fx))
        if prices.empty:
            continue
        for idx in group.index:
            for h in RETURN_HORIZONS:
                result = _forward_return_after(prices, out.loc[idx, "available_date"], h)
                value = _finite(result.get("return"))
                if np.isfinite(value):
                    out.loc[idx, f"return_{h}w"] = value
    return out


def _stage_baseline(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stage in ("WATCH", "EARLY", "ACTIVE"):
        subset = events[events["cot_stage"].eq(stage) & events["cot_pair_direction"].ne(0)].copy()
        if subset.empty:
            continue
        direction = subset["cot_pair_direction"].astype(int)
        for h in RETURN_HORIZONS:
            rows.append({"COT Stage": stage, "Horizont": f"{h}W", **_metrics(subset, direction, h)})
    return pd.DataFrame(rows)


def _alignment_ladder(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scenarios = [
        ("COT baseline", lambda f: pd.Series(True, index=f.index)),
        ("+ 20D STRONG/EXTREME aligned", lambda f: f["relationship"].eq("ALIGNED") & f["rates_strength"].isin(["STRONG", "EXTREME"])),
        ("+ 20D EXTREME aligned", lambda f: f["relationship"].eq("ALIGNED") & f["rates_strength"].eq("EXTREME")),
        ("+ strong 20D + 5D confirms", lambda f: f["relationship"].eq("ALIGNED") & f["rates_strength"].isin(["STRONG", "EXTREME"]) & f["confirm5"].eq(1)),
        ("+ strong 20D + 60D confirms", lambda f: f["relationship"].eq("ALIGNED") & f["rates_strength"].isin(["STRONG", "EXTREME"]) & f["confirm60"].eq(1)),
        ("+ strong 20D + 5D + 60D", lambda f: f["relationship"].eq("ALIGNED") & f["rates_strength"].isin(["STRONG", "EXTREME"]) & f["confirm5"].eq(1) & f["confirm60"].eq(1)),
    ]
    for stage in ("WATCH", "EARLY", "ACTIVE"):
        frame = events[events["cot_stage"].eq(stage) & events["cot_pair_direction"].ne(0)].copy()
        if frame.empty:
            continue
        baselines = {}
        for name, mask_fn in scenarios:
            subset = frame[mask_fn(frame)].copy()
            if subset.empty:
                continue
            direction = subset["cot_pair_direction"].astype(int)
            for h in RETURN_HORIZONS:
                m = _metrics(subset, direction, h)
                if name == "COT baseline":
                    baselines[h] = m
                base = baselines.get(h, {})
                rows.append({
                    "COT Stage": stage, "Scenario": name, "Horizont": f"{h}W", **m,
                    "Δ Hit vs COT": (_finite(m.get("Hit Rate")) - _finite(base.get("Hit Rate"))
                                     if np.isfinite(_finite(m.get("Hit Rate"))) and np.isfinite(_finite(base.get("Hit Rate"))) else np.nan),
                    "Δ Median vs COT": (_finite(m.get("Median Return")) - _finite(base.get("Median Return"))
                                        if np.isfinite(_finite(m.get("Median Return"))) and np.isfinite(_finite(base.get("Median Return"))) else np.nan),
                })
    return pd.DataFrame(rows)


def _conflicts(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stage in ("EARLY", "ACTIVE"):
        subset = events[
            events["cot_stage"].eq(stage)
            & events["relationship"].eq("CONFLICT")
            & events["rates_strength"].isin(["STRONG", "EXTREME"])
            & events["cot_pair_direction"].ne(0)
        ].copy()
        if subset.empty:
            continue
        for label, direction in (
            ("follow COT", subset["cot_pair_direction"].astype(int)),
            ("follow Rates", subset["rates20_raw_direction"].astype(int)),
        ):
            for h in RETURN_HORIZONS:
                rows.append({"COT Stage": stage, "Conflict View": label, "Horizont": f"{h}W",
                             **_metrics(subset, direction, h)})
    return pd.DataFrame(rows)


def run_regime_aware_event_study(v3190_result: Mapping[str, Any]) -> dict[str, Any]:
    weekly = pd.DataFrame(v3190_result.get("weekly", pd.DataFrame()))
    if weekly.empty:
        return {"meta": {}, "stage_baseline": pd.DataFrame(), "alignment_ladder": pd.DataFrame(),
                "conflicts": pd.DataFrame(), "events": pd.DataFrame()}
    enriched = _prepare_weekly(weekly)
    events = enriched[enriched["event_start"] & ~enriched["relationship"].eq("NEUTRAL")].copy()
    events = _attach_returns(events)
    return {
        "meta": {
            "events": int(len(events)),
            "watch": int(events["cot_stage"].eq("WATCH").sum()),
            "early": int(events["cot_stage"].eq("EARLY").sum()),
            "active": int(events["cot_stage"].eq("ACTIVE").sum()),
        },
        "stage_baseline": _stage_baseline(events),
        "alignment_ladder": _alignment_ladder(events),
        "conflicts": _conflicts(events),
        "events": events,
    }
