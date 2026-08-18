from __future__ import annotations

from typing import Any, Mapping

import numpy as np


UPPER = 80.0
LOWER = 20.0
WATCH_MARGIN = 10.0


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _dir_text(direction: int) -> str:
    return "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"


def commercial_156w_pressure(
    percentile: float,
    delta_1w: float = np.nan,
    delta_2w: float = np.nan,
    delta_4w: float = np.nan,
    *,
    upper: float = UPPER,
    lower: float = LOWER,
    watch_margin: float = WATCH_MARGIN,
) -> dict:
    """Slow Commercial regime pressure.

    80/20 are the existing fixed structural boundaries. The 10-point watch
    margin only means "approaching the existing boundary"; it is not a new
    trade-signal threshold.

    Level and slope remain separate:
      - level = current 156W Commercial Net percentile
      - slope = sign consistency across Δ1W / Δ2W / Δ4W
    """
    pct = _finite(percentile)
    deltas = [_finite(delta_1w), _finite(delta_2w), _finite(delta_4w)]
    valid = [x for x in deltas if np.isfinite(x)]

    positive_votes = sum(x > 0 for x in valid)
    negative_votes = sum(x < 0 for x in valid)

    if len(valid) >= 2 and positive_votes >= 2:
        slope_direction = 1
        slope_label = "RISING"
    elif len(valid) >= 2 and negative_votes >= 2:
        slope_direction = -1
        slope_label = "FALLING"
    else:
        slope_direction = 0
        slope_label = "MIXED / FLAT"

    if not np.isfinite(pct):
        return {
            "direction": 0,
            "label": "N/V",
            "level_label": "N/V",
            "slope_direction": slope_direction,
            "slope_label": slope_label,
            "interesting": False,
            "near_extreme": False,
        }

    if pct >= upper:
        direction = 1
        level_label = "EXTREME BULLISH"
        if slope_direction < 0:
            label = "STRONG BULLISH · FADING"
        elif slope_direction > 0:
            label = "STRONG BULLISH · BUILDING"
        else:
            label = "STRONG BULLISH"
        interesting = True
        near_extreme = True

    elif pct <= lower:
        direction = -1
        level_label = "EXTREME BEARISH"
        if slope_direction > 0:
            label = "STRONG BEARISH · RECOVERING"
        elif slope_direction < 0:
            label = "STRONG BEARISH · BUILDING"
        else:
            label = "STRONG BEARISH"
        interesting = True
        near_extreme = True

    elif pct >= upper - watch_margin and slope_direction > 0:
        direction = 1
        level_label = "NEAR BULLISH EXTREME"
        label = "BULLISH BUILDING"
        interesting = True
        near_extreme = True

    elif pct <= lower + watch_margin and slope_direction < 0:
        direction = -1
        level_label = "NEAR BEARISH EXTREME"
        label = "BEARISH BUILDING"
        interesting = True
        near_extreme = True

    else:
        direction = 0
        level_label = "MID RANGE"
        label = (
            "RISING · NOT EXTREME"
            if slope_direction > 0
            else "FALLING · NOT EXTREME"
            if slope_direction < 0
            else "NEUTRAL"
        )
        interesting = False
        near_extreme = False

    return {
        "direction": int(direction),
        "label": label,
        "level_label": level_label,
        "slope_direction": int(slope_direction),
        "slope_label": slope_label,
        "positive_slope_votes": int(positive_votes),
        "negative_slope_votes": int(negative_votes),
        "interesting": bool(interesting),
        "near_extreme": bool(near_extreme),
    }


def cot_26w_timing(
    commercial_index: float,
    retail_index: float = np.nan,
    *,
    upper: float = 90.0,
    lower: float = 10.0,
) -> dict:
    """Strict 90/10 current-state compatibility context.

    The trader watchlist itself uses historical 90/10 ENTRY triggers.
    """
    comm = _finite(commercial_index)
    if np.isfinite(comm) and comm >= upper:
        return {
            "direction": 1,
            "label": "BULLISH EXTREME",
            "strength": "COMMERCIAL 26W 90/10",
            "interesting": True,
        }
    if np.isfinite(comm) and comm <= lower:
        return {
            "direction": -1,
            "label": "BEARISH EXTREME",
            "strength": "COMMERCIAL 26W 90/10",
            "interesting": True,
        }
    return {
        "direction": 0,
        "label": "NO CURRENT 90/10 EXTREME",
        "strength": "NO COMMERCIAL 26W 90/10",
        "interesting": False,
    }




def combine_dual_horizon(
    long_term: Mapping[str, Any],
    short_term: Mapping[str, Any],
    *,
    hard_regime_direction: int = 0,
    hard_regime_stage: int = 0,
) -> dict:
    """Combine slow 156W pressure with fast 26W timing.

    Existing confirmed hard regime always wins. 26W remains timing/context and
    cannot reverse a confirmed regime by itself.
    """
    long_dir = int(np.sign(long_term.get("direction", 0) or 0))
    short_dir = int(np.sign(short_term.get("direction", 0) or 0))
    hard_dir = int(np.sign(hard_regime_direction or 0))
    stage = max(0, int(hard_regime_stage or 0))

    if stage >= 4 and hard_dir != 0:
        regime = f"{_dir_text(hard_dir)} REGIME"
        if short_dir == -hard_dir:
            return {
                "interpretation": f"{regime} · SHORT-TERM CORRECTION",
                "action": "KORREKTUR / PULLBACK ABWARTEN",
                "tone": "warn",
            }
        if short_dir == hard_dir:
            return {
                "interpretation": f"{regime} · 26W TIMING ALIGNED",
                "action": "REGIME BESTÄTIGT · S&D / SETUP PRÜFEN",
                "tone": "good",
            }
        return {
            "interpretation": f"{regime} · TIMING NEUTRAL",
            "action": "AUF 26W TIMING WARTEN",
            "tone": "neutral",
        }

    if long_dir > 0 and short_dir < 0:
        return {
            "interpretation": "BEARISH CONTINUATION · BULLISH TRANSITION WATCH",
            "action": "KORREKTUR WEITER MÖGLICH · LONG NOCH NICHT FREI",
            "tone": "warn",
        }
    if long_dir < 0 and short_dir > 0:
        return {
            "interpretation": "BULLISH CONTINUATION · BEARISH TRANSITION WATCH",
            "action": "ANSTIEG WEITER MÖGLICH · SHORT NOCH NICHT FREI",
            "tone": "warn",
        }

    if long_dir != 0 and short_dir == long_dir:
        return {
            "interpretation": f"{_dir_text(long_dir)} PRESSURE · 26W ALIGNED",
            "action": "BESTÄTIGUNG / REGIME-STUFE BEOBACHTEN",
            "tone": "good",
        }

    if long_dir != 0 and short_dir == 0:
        return {
            "interpretation": f"{_dir_text(long_dir)} REGIME PRESSURE · WAIT TIMING",
            "action": "AUF 26W EXTREM / TIMING WARTEN",
            "tone": "neutral",
        }

    if long_dir == 0 and short_dir != 0:
        return {
            "interpretation": f"{_dir_text(short_dir)} 26W EXTREME · 156W NEUTRAL",
            "action": "KURZFRISTIGEN MOVE BEOBACHTEN · KEIN REGIMEWECHSEL",
            "tone": "neutral",
        }

    return {
        "interpretation": "NO DUAL-HORIZON EDGE",
        "action": "WARTEN",
        "tone": "neutral",
    }


def classify_watchlist_row(
    row: Mapping[str, Any],
    *,
    hard_regime_direction: int = 0,
    hard_regime_stage: int = 0,
) -> dict:
    long_term = commercial_156w_pressure(
        row.get("commercial_net_percentile"),
        row.get("commercial_percentile_change_1w"),
        row.get("commercial_percentile_change_2w"),
        row.get("commercial_percentile_change_4w"),
    )
    short_term = cot_26w_timing(
        row.get("commercial_index"),
        row.get("retail_index"),
    )
    combined = combine_dual_horizon(
        long_term,
        short_term,
        hard_regime_direction=hard_regime_direction,
        hard_regime_stage=hard_regime_stage,
    )

    interesting = bool(
        long_term["interesting"]
        or short_term["interesting"]
        or int(hard_regime_stage or 0) > 0
    )

    return {
        "long_term": long_term,
        "short_term": short_term,
        "combined": combined,
        "interesting": interesting,
    }
