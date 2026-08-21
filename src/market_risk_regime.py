from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from .watchlist_macro_micro import classify_macro_micro_trade

RISK_BUCKETS = (
    {"bucket": "Equities", "members": (("ES", 1), ("NQ", 1), ("YM", 1), ("RTY", 1))},
    {"bucket": "Growth / Cyclicals", "members": (("HG", 1), ("CL", 1), ("LBR", 1), ("BTC", 1))},
    {"bucket": "Risk FX", "members": (("AUD", 1), ("NZD", 1), ("CAD", 1), ("MXN", 1))},
    {"bucket": "Safe Havens", "members": (("JPY", -1), ("CHF", -1))},
    {"bucket": "Rates / Liquidity", "members": (("ZT", -1), ("ZF", -1), ("ZN", -1), ("ZB", -1), ("UB", -1))},
)


def _finite(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return np.nan
    return out if np.isfinite(out) else np.nan


def _find_market(frame: pd.DataFrame, symbol: str) -> Mapping[str, Any] | None:
    if frame is None or frame.empty:
        return None
    target = str(symbol).upper().strip()
    for column in ("symbol", "ticker", "market_symbol", "cot_symbol"):
        if column not in frame.columns:
            continue
        values = frame[column].astype(str).str.upper().str.strip()
        exact = frame.loc[values == target]
        if not exact.empty:
            return exact.iloc[0]
    return None


def _direction_label(direction: int) -> str:
    return "RISK-ON" if direction > 0 else "RISK-OFF" if direction < 0 else "MIXED"


def _bucket_vote(votes: list[int]) -> tuple[int, str]:
    valid = [int(v) for v in votes if int(v) != 0]
    if not valid:
        return 0, "MIXED"
    total = int(sum(valid))
    direction = 1 if total > 0 else -1 if total < 0 else 0
    return direction, _direction_label(direction)


def _global_regime(directions: list[int]) -> str:
    valid = [int(v) for v in directions if int(v) != 0]
    if not valid:
        return "MIXED"
    score = int(sum(valid))
    if score >= 4:
        return "STRONG RISK-ON"
    if score >= 2:
        return "RISK-ON"
    if score <= -4:
        return "STRONG RISK-OFF"
    if score <= -2:
        return "RISK-OFF"
    return "MIXED"


def build_market_risk_regime(all_markets: pd.DataFrame, *, classifier: Callable[[Mapping[str, Any]], Mapping[str, Any]] = classify_macro_micro_trade) -> dict:
    frame = all_markets.copy() if isinstance(all_markets, pd.DataFrame) else pd.DataFrame(all_markets or [])
    bucket_rows: list[dict] = []
    for spec in RISK_BUCKETS:
        macro_votes: list[int] = []
        micro_votes: list[int] = []
        commercial_votes: list[int] = []
        covered = 0
        for symbol, polarity in spec["members"]:
            row = _find_market(frame, symbol)
            if row is None:
                continue
            covered += 1
            decision = dict(classifier(row) or {})
            macro = dict(decision.get("macro") or {})
            micro = dict(decision.get("micro") or {})
            macro_votes.append(int(macro.get("direction", 0) or 0) * int(polarity))
            micro_votes.append(int(micro.get("direction", 0) or 0) * int(polarity))
            commercial_4w = _finite(row.get("commercial_change_4w"))
            if np.isfinite(commercial_4w):
                commercial_votes.append((1 if commercial_4w > 0 else -1 if commercial_4w < 0 else 0) * int(polarity))
        macro_direction, macro_label = _bucket_vote(macro_votes)
        micro_direction, micro_label = _bucket_vote(micro_votes)
        commercial_direction, commercial_label = _bucket_vote(commercial_votes)
        bucket_rows.append({
            "bucket": spec["bucket"],
            "macro_direction": macro_direction,
            "macro": macro_label,
            "micro_direction": micro_direction,
            "micro": micro_label,
            "commercial_direction": commercial_direction,
            "commercial_flow": commercial_label,
            "coverage": int(covered),
            "members": int(len(spec["members"])),
        })
    macro_directions = [int(row["macro_direction"]) for row in bucket_rows]
    micro_directions = [int(row["micro_direction"]) for row in bucket_rows]
    commercial_directions = [int(row["commercial_direction"]) for row in bucket_rows]
    macro_regime = _global_regime(macro_directions)
    micro_pulse = _global_regime(micro_directions)
    commercial_flow = _global_regime(commercial_directions)
    macro_sign = 1 if "RISK-ON" in macro_regime else -1 if "RISK-OFF" in macro_regime else 0
    commercial_sign = 1 if "RISK-ON" in commercial_flow else -1 if "RISK-OFF" in commercial_flow else 0
    micro_sign = 1 if "RISK-ON" in micro_pulse else -1 if "RISK-OFF" in micro_pulse else 0
    if macro_sign != 0 and commercial_sign == -macro_sign and micro_sign == -macro_sign:
        pressure = "TRANSITION PRESSURE"
    elif macro_sign != 0 and commercial_sign == -macro_sign:
        pressure = "ROTATION WARNING"
    elif macro_sign != 0 and commercial_sign == macro_sign:
        pressure = "STABLE"
    else:
        pressure = "MIXED"
    available_buckets = sum(int(row["coverage"]) > 0 for row in bucket_rows)
    aligned_macro_buckets = sum(int(row["macro_direction"]) == macro_sign and macro_sign != 0 for row in bucket_rows)
    breadth = f"{aligned_macro_buckets}/{available_buckets}" if available_buckets else "0/0"
    return {
        "regime": macro_regime,
        "micro_pulse": micro_pulse,
        "commercial_flow": commercial_flow,
        "pressure": pressure,
        "breadth": breadth,
        "available_buckets": int(available_buckets),
        "buckets": pd.DataFrame(bucket_rows),
    }
