from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from .watchlist_macro_micro import macro_156w_state
from .yield_spreads import pair_spread_snapshot


# V3.17.0 · FUNDAMENTAL CURRENCY STRENGTH
# Research-only combination:
#   COT 156W = positioning / macro structure
#   2Y rates = historically normalized fundamental repricing

RATES_CURRENCY_ORDER = (
    "EUR", "GBP", "AUD", "NZD", "USD", "CAD", "JPY", "CHF", "MXN"
)
HORIZONS = (5, 20, 60)
MEANINGFUL_PERCENTILE = 75.0
MIN_MEANINGFUL_COMPARISONS = 2

STATE_PRIORITY = {
    "ALIGNED": 0,
    "RATES LEAD": 1,
    "COT LEADS": 2,
    "CONFLICT": 3,
    "NEUTRAL": 4,
}
STATE_ICON = {
    "ALIGNED": "🟢",
    "RATES LEAD": "🟣",
    "COT LEADS": "🔵",
    "CONFLICT": "🔴",
    "NEUTRAL": "⚪",
}


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _direction_word(direction: int) -> str:
    if direction > 0:
        return "BULLISH"
    if direction < 0:
        return "BEARISH"
    return "NEUTRAL"


def _strength_from_percentile(percentile: Any) -> str:
    value = _finite(percentile)
    if not np.isfinite(value):
        return "N/V"
    if value >= 90.0:
        return "EXTREME"
    if value >= 75.0:
        return "STRONG"
    if value >= 60.0:
        return "MILD"
    return "NORMAL"


def _result_has_series(result: Any) -> bool:
    series = getattr(result, "series", None)
    if series is None:
        return False
    try:
        return not series.empty
    except Exception:
        return False


def _available_rate_currencies(
    universe: Mapping[str, Any],
    requested: Sequence[str] | None = None,
) -> list[str]:
    order = tuple(requested or RATES_CURRENCY_ORDER)
    return [
        currency
        for currency in order
        if currency in universe and _result_has_series(universe.get(currency))
    ]


def _horizon_consensus(
    currency: str,
    universe: Mapping[str, Any],
    *,
    horizon: int,
    comparison_currencies: Sequence[str] | None = None,
    snapshot_fn: Callable[
        [str, Mapping[str, Any]], Mapping[str, Any]
    ] = pair_spread_snapshot,
) -> dict:
    """Basket-relative rates direction without an arbitrary weighted score.

    For each available peer, create a direct spread with ``currency`` as base.
    Only same-horizon moves at/above the historical 75th percentile cast a
    directional vote. 20D is later used as the primary swing view.
    """
    if horizon not in HORIZONS:
        raise ValueError(f"Unsupported horizon: {horizon}")

    available = _available_rate_currencies(
        universe,
        comparison_currencies,
    )
    peers = [other for other in available if other != currency]

    delta_key = f"delta_{horizon}d_bp"
    percentile_key = f"percentile_{horizon}d"

    observations = []
    for peer in peers:
        try:
            snap = dict(
                snapshot_fn(f"{currency}{peer}", universe) or {}
            )
        except Exception:
            continue

        if not bool(snap.get("available", False)):
            continue

        delta = _finite(snap.get(delta_key))
        percentile = _finite(snap.get(percentile_key))
        if not np.isfinite(delta) or not np.isfinite(percentile):
            continue

        observations.append(
            {
                "peer": peer,
                "delta_bp": float(delta),
                "percentile": float(percentile),
                "direction": (
                    1 if delta > 0 else -1 if delta < 0 else 0
                ),
                "meaningful": bool(
                    percentile >= MEANINGFUL_PERCENTILE
                    and delta != 0
                ),
            }
        )

    available_count = len(observations)
    meaningful = [x for x in observations if x["meaningful"]]
    bullish = [x for x in meaningful if x["direction"] > 0]
    bearish = [x for x in meaningful if x["direction"] < 0]

    direction = 0
    winners = []
    if len(meaningful) >= MIN_MEANINGFUL_COMPARISONS:
        if len(bullish) > len(bearish):
            direction = 1
            winners = bullish
        elif len(bearish) > len(bullish):
            direction = -1
            winners = bearish

    winning_percentile = (
        float(np.median([x["percentile"] for x in winners]))
        if winners
        else np.nan
    )
    strength = _strength_from_percentile(winning_percentile)

    if available_count == 0:
        label = "N/V"
    elif direction == 0:
        label = (
            f"NEUTRAL · {len(meaningful)}/{available_count} signifikant"
        )
    else:
        label = (
            f"{_direction_word(direction)} · "
            f"{len(winners)}/{available_count} · {strength}"
        )

    return {
        "direction": int(direction),
        "label": label,
        "strength": strength,
        "median_winning_percentile": winning_percentile,
        "available_comparisons": int(available_count),
        "meaningful_comparisons": int(len(meaningful)),
        "bullish_votes": int(len(bullish)),
        "bearish_votes": int(len(bearish)),
        "observations": observations,
    }


def _rates_alignment(
    horizons: Mapping[int, Mapping[str, Any]],
) -> str:
    directions = {
        horizon: int(
            (horizons.get(horizon) or {}).get("direction", 0) or 0
        )
        for horizon in HORIZONS
    }
    bull = sum(value > 0 for value in directions.values())
    bear = sum(value < 0 for value in directions.values())

    if bull == 0 and bear == 0:
        return "0/3 · NEUTRAL"
    if bull > bear:
        suffix = " · mixed" if bear else ""
        return f"{bull}/3 · BULLISH{suffix}"
    if bear > bull:
        suffix = " · mixed" if bull else ""
        return f"{bear}/3 · BEARISH{suffix}"
    return "MIXED"


def _micro_label(row: Mapping[str, Any]) -> str:
    direction_value = _finite(row.get("micro_trigger_direction"))
    direction = (
        int(np.sign(direction_value))
        if np.isfinite(direction_value)
        else 0
    )
    age = _finite(row.get("micro_trigger_age_weeks"))
    fresh = bool(row.get("micro_trigger_fresh", False))

    if direction == 0:
        return "—"

    text = "Bullish" if direction > 0 else "Bearish"
    if not np.isfinite(age) or int(age) < 0:
        return text

    age_int = int(age)
    age_text = (
        "diese Woche" if age_int == 0 else f"vor {age_int}W"
    )
    fresh_text = " · fresh" if fresh else ""
    return f"{text} · {age_text}{fresh_text}"


def _classify_fundamental_state(
    *,
    cot_direction: int,
    cot_phase: str,
    cot_active: bool,
    rates_20d: Mapping[str, Any],
) -> tuple[str, int]:
    rates_available = (
        int(rates_20d.get("available_comparisons", 0) or 0) > 0
    )
    rates_direction = int(rates_20d.get("direction", 0) or 0)
    rates_meaningful = int(
        rates_20d.get("meaningful_comparisons", 0) or 0
    )
    rates_robust = (
        rates_direction != 0
        and rates_meaningful >= MIN_MEANINGFUL_COMPARISONS
    )

    if not rates_available:
        return "NEUTRAL", 0

    if rates_robust and cot_direction != 0:
        if rates_direction == cot_direction:
            if cot_active:
                return "ALIGNED", cot_direction
            return "RATES LEAD", rates_direction
        return "CONFLICT", 0

    if rates_robust and cot_direction == 0:
        return "RATES LEAD", rates_direction

    if (
        cot_direction != 0
        and not rates_robust
        and str(cot_phase).upper()
        in {"TRANSITION", "RELEASE", "CONFIRMED"}
    ):
        return "COT LEADS", cot_direction

    return "NEUTRAL", 0


def _interpretation(
    currency: str,
    state: str,
    direction: int,
    cot_phase: str,
    rates_20d: Mapping[str, Any],
) -> str:
    direction_word = (
        "bullish"
        if direction > 0
        else "bearish"
        if direction < 0
        else "neutral"
    )

    if state == "ALIGNED":
        return (
            f"COT-Makro und historisch starkes 20D-Rates-Repricing "
            f"zeigen beide {direction_word} für {currency}. "
            "Das ist die stärkste gemeinsame Bestätigung."
        )
    if state == "RATES LEAD":
        return (
            f"Die 2Y-Rates bewegen sich bereits historisch auffällig "
            f"zugunsten {currency}; COT ist noch nicht im aktiven "
            "Release/Confirmed-Zustand. Möglicher fundamentaler Vorlauf."
        )
    if state == "COT LEADS":
        return (
            f"COT zeigt für {currency} bereits {direction_word} "
            f"({cot_phase}), während das 20D-Rates-Repricing noch "
            "keine robuste historische Bestätigung liefert."
        )
    if state == "CONFLICT":
        return (
            f"COT und 20D-Rates laufen bei {currency} gegeneinander. "
            "Kein sauberes fundamentales Alignment."
        )

    if int(rates_20d.get("available_comparisons", 0) or 0) == 0:
        return (
            f"Für {currency} ist aktuell kein ausreichend nutzbarer "
            "2Y-Rates-Vergleich verfügbar; deshalb wird kein "
            "Lead/Alignment behauptet."
        )
    return (
        f"Bei {currency} gibt es aktuell noch kein robustes "
        "gemeinsames COT-/Rates-Signal."
    )


def build_fundamental_currency_strength(
    profiles: pd.DataFrame,
    universe: Mapping[str, Any],
    *,
    comparison_currencies: Sequence[str] | None = None,
    snapshot_fn: Callable[
        [str, Mapping[str, Any]], Mapping[str, Any]
    ] = pair_spread_snapshot,
) -> pd.DataFrame:
    """Combine current COT structure with normalized 2Y rates."""
    if profiles is None or profiles.empty:
        return pd.DataFrame()

    rows = []
    for _, source in profiles.iterrows():
        row = source.to_dict()
        currency = str(row.get("symbol", "") or "").upper().strip()
        if not currency:
            continue

        macro = macro_156w_state(row)
        cot_direction = int(macro.get("direction", 0) or 0)
        cot_phase = str(
            macro.get("phase", "NEUTRAL") or "NEUTRAL"
        ).upper()
        cot_active = bool(macro.get("active", False))

        horizons = {
            horizon: _horizon_consensus(
                currency,
                universe,
                horizon=horizon,
                comparison_currencies=comparison_currencies,
                snapshot_fn=snapshot_fn,
            )
            for horizon in HORIZONS
        }
        rates_20d = horizons[20]

        state, bias_direction = _classify_fundamental_state(
            cot_direction=cot_direction,
            cot_phase=cot_phase,
            cot_active=cot_active,
            rates_20d=rates_20d,
        )

        state_display = f"{STATE_ICON[state]} {state}"
        if bias_direction != 0 and state != "CONFLICT":
            state_display += (
                f" · {_direction_word(bias_direction)}"
            )

        micro_direction_value = _finite(
            row.get("micro_trigger_direction")
        )
        micro_direction = (
            int(np.sign(micro_direction_value))
            if np.isfinite(micro_direction_value)
            else 0
        )

        rows.append(
            {
                "symbol": currency,
                "market_name": str(
                    row.get("market_name", currency) or currency
                ),
                "fundamental_state": state,
                "state_display": state_display,
                "bias_direction": int(bias_direction),
                "bias_label": (
                    _direction_word(bias_direction)
                    if bias_direction
                    else "MIXED / NEUTRAL"
                ),
                "cot_direction": int(cot_direction),
                "cot_phase": cot_phase,
                "cot_active": cot_active,
                "cot_macro_label": str(
                    macro.get("label", "NEUTRAL") or "NEUTRAL"
                ),
                "micro_direction": int(micro_direction),
                "micro_label": _micro_label(row),
                "micro_fresh": bool(
                    row.get("micro_trigger_fresh", False)
                ),
                "cot_cycle_entry_date": row.get(
                    "cot_cycle_entry_date"
                ),
                "cot_release_date": row.get("cot_release_date"),
                "rates_5d_direction": int(
                    horizons[5]["direction"]
                ),
                "rates_5d_label": str(horizons[5]["label"]),
                "rates_5d_strength": str(horizons[5]["strength"]),
                "rates_20d_direction": int(
                    horizons[20]["direction"]
                ),
                "rates_20d_label": str(horizons[20]["label"]),
                "rates_20d_strength": str(
                    horizons[20]["strength"]
                ),
                "rates_20d_percentile": horizons[20][
                    "median_winning_percentile"
                ],
                "rates_20d_available": int(
                    horizons[20]["available_comparisons"]
                ),
                "rates_20d_meaningful": int(
                    horizons[20]["meaningful_comparisons"]
                ),
                "rates_60d_direction": int(
                    horizons[60]["direction"]
                ),
                "rates_60d_label": str(horizons[60]["label"]),
                "rates_60d_strength": str(
                    horizons[60]["strength"]
                ),
                "rates_alignment": _rates_alignment(horizons),
                "interpretation": _interpretation(
                    currency,
                    state,
                    int(bias_direction),
                    cot_phase,
                    rates_20d,
                ),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["_state_order"] = (
        out["fundamental_state"]
        .map(STATE_PRIORITY)
        .fillna(99)
    )
    out["_rates_order"] = pd.to_numeric(
        out["rates_20d_percentile"],
        errors="coerce",
    ).fillna(-1.0)

    return (
        out.sort_values(
            ["_state_order", "_rates_order", "symbol"],
            ascending=[True, False, True],
        )
        .drop(columns=["_state_order", "_rates_order"])
        .reset_index(drop=True)
    )


__all__ = [
    "build_fundamental_currency_strength",
    "MEANINGFUL_PERCENTILE",
    "MIN_MEANINGFUL_COMPARISONS",
    "STATE_PRIORITY",
]
