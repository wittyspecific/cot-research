from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


CURRENCY_ORDER = (
    "EUR",
    "GBP",
    "AUD",
    "NZD",
    "USD",
    "CAD",
    "CHF",
    "MXN",
    "JPY",
)

CURRENCY_NAMES_DE = {
    "EUR": "Euro",
    "GBP": "Britisches Pfund",
    "AUD": "Australischer Dollar",
    "NZD": "Neuseeland-Dollar",
    "USD": "US-Dollar",
    "CAD": "Kanadischer Dollar",
    "CHF": "Schweizer Franken",
    "MXN": "Mexikanischer Peso",
    "BRL": "Brasilianischer Real",
    "ZAR": "Südafrikanischer Rand",
    "JPY": "Japanischer Yen",
}

FX_SEASONALITY_HISTORY_YEARS = 20
FX_SEASONALITY_FORWARD_DAYS = (20, 40, 60)
FX_SEASONALITY_MIN_YEARS = 8


def _finite(value) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def currency_cot_profile(
    *,
    symbol: str,
    market_name: str,
    report_date,
    commercial_index,
    commercial_net_percentile,
    noncommercial_net_percentile=np.nan,
    retail_net_percentile=np.nan,
    cycle_phase: str | None = None,
    cycle_direction: int = 0,
    extreme_direction: int = 0,
    cycle_state: str | None = None,
    transition_state: str | None = None,
    extreme_percentile=np.nan,
    percentile_change_1w=np.nan,
    percentile_change_4w=np.nan,
    index_upper: float = 80.0,
    index_lower: float = 20.0,
    net_upper: float = 80.0,
    net_lower: float = 20.0,
) -> dict:
    """Return a transparent currency COT profile using release semantics.

    V3.10.0 uses Commercial Net Percentile 156W as the primary state:
      * an upper/lower 156W percentile extreme is a hedge STATE only;
      * direction becomes active only after that percentile leaves the extreme;
      * the 26W COT index remains descriptive/advanced research.
    """
    cot = float(commercial_index) if _finite(commercial_index) else np.nan
    comm = float(commercial_net_percentile) if _finite(commercial_net_percentile) else np.nan
    nc = float(noncommercial_net_percentile) if _finite(noncommercial_net_percentile) else np.nan
    retail = float(retail_net_percentile) if _finite(retail_net_percentile) else np.nan

    phase = str(cycle_phase or "").upper()
    direction = int(cycle_direction or 0) if phase == "RELEASE" else 0
    extreme_dir = int(extreme_direction or 0)
    release_ok = direction != 0

    extreme_pct = (
        float(extreme_percentile)
        if _finite(extreme_percentile)
        else comm if direction != 0 and np.isfinite(comm) else np.nan
    )
    comm_ok = nc_ok = retail_ok = False
    if direction > 0:
        # Commercial confirmation belongs to the extreme episode that just
        # released; the current percentile is already below the upper boundary.
        comm_ok = np.isfinite(extreme_pct) and extreme_pct >= float(net_upper)
        nc_ok = np.isfinite(nc) and nc <= float(net_lower)
        retail_ok = np.isfinite(retail) and retail <= float(net_lower)
    elif direction < 0:
        comm_ok = np.isfinite(extreme_pct) and extreme_pct <= float(net_lower)
        nc_ok = np.isfinite(nc) and nc >= float(net_upper)
        retail_ok = np.isfinite(retail) and retail >= float(net_upper)

    confirmations = int(release_ok) + int(comm_ok) + int(nc_ok) + int(retail_ok)
    signed_strength = int(direction * confirmations)
    bias = "BULLISH" if direction > 0 else "BÄRISCH" if direction < 0 else "NEUTRAL"

    if phase == "EXTREME":
        state_label = "FULL HEDGE" if extreme_dir > 0 else "LOW HEDGE" if extreme_dir < 0 else "EXTREM"
        signal_label = "WAITING FOR RELEASE"
    elif phase == "RELEASE":
        state_label = str(cycle_state or "RELEASE")
        signal_label = "BULLISH RELEASE" if direction > 0 else "BEARISH RELEASE"
    else:
        state_label = str(cycle_state or "NEUTRAL")
        signal_label = "NO SIGNAL"

    return {
        "symbol": symbol,
        "market_name": market_name,
        "report_date": report_date,
        "commercial_index": cot,
        "commercial_net_percentile": comm,
        "noncommercial_net_percentile": nc,
        "retail_net_percentile": retail,
        "cycle_phase": phase or "NONE",
        "cycle_state": str(cycle_state or ""),
        "transition_state": str(transition_state or ""),
        "extreme_percentile": extreme_pct,
        "percentile_change_1w": float(percentile_change_1w) if _finite(percentile_change_1w) else np.nan,
        "percentile_change_4w": float(percentile_change_4w) if _finite(percentile_change_4w) else np.nan,
        "extreme_direction": extreme_dir,
        "state_label": state_label,
        "signal_label": signal_label,
        "direction": direction,
        "confirmations": confirmations,
        "signed_strength": signed_strength,
        "bias": bias,
        "cot_ok": bool(release_ok),
        "release_ok": bool(release_ok),
        "commercial_ok": bool(comm_ok),
        "noncommercial_ok": bool(nc_ok),
        "retail_ok": bool(retail_ok),
    }


def pair_bias_from_strength(
    base_strength: int,
    quote_strength: int,
) -> dict:
    """
    pair_edge = base_strength - quote_strength

    +4 CAD vs -4 CHF -> +8 -> STARK BULLISH
    +3 CAD vs -3 CHF -> +6 -> STARK BULLISH
    +1 AUD vs -1 CAD -> +2 -> LEICHT BULLISH
    """
    edge = int(base_strength) - int(quote_strength)
    magnitude = abs(edge)

    if edge == 0:
        return {
            "edge": 0,
            "direction": 0,
            "strength_label": "NEUTRAL",
            "trade_bias": "NEUTRAL",
            "display": "— NEUTRAL",
        }

    direction = 1 if edge > 0 else -1

    if magnitude >= 6:
        strength_word = "STARK"
    elif magnitude >= 3:
        strength_word = ""
    else:
        strength_word = "LEICHT"

    direction_word = "BULLISH" if direction > 0 else "BÄRISCH"
    strength_label = (
        f"{strength_word} {direction_word}"
        if strength_word
        else direction_word
    )

    return {
        "edge": edge,
        "direction": direction,
        "strength_label": strength_label,
        "trade_bias": "LONG-BIAS" if direction > 0 else "SHORT-BIAS",
        "display": (
            f"▲ {strength_label}"
            if direction > 0
            else f"▼ {strength_label}"
        ),
    }


def _currency_state_text(row: pd.Series) -> str:
    confirmations = int(row["confirmations"])
    if confirmations == 0:
        return f"{row['symbol']} · NEUTRAL"
    return f"{row['symbol']} · {row['bias']} {confirmations}/4"


def build_all_fx_pairs(profiles: pd.DataFrame) -> pd.DataFrame:
    if profiles is None or profiles.empty:
        return pd.DataFrame()

    by_symbol = {
        str(row["symbol"]): row
        for _, row in profiles.iterrows()
    }

    available = [
        symbol
        for symbol in CURRENCY_ORDER
        if symbol in by_symbol
    ]

    rows = []
    for base, quote in combinations(available, 2):
        base_row = by_symbol[base]
        quote_row = by_symbol[quote]
        pair_bias = pair_bias_from_strength(
            int(base_row["signed_strength"]),
            int(quote_row["signed_strength"]),
        )

        rows.append(
            {
                "pair": f"{base}{quote}",
                "base": base,
                "quote": quote,
                "pair_direction": pair_bias["direction"],
                "pair_edge": pair_bias["edge"],
                "pair_strength": pair_bias["strength_label"],
                "trade_bias": pair_bias["trade_bias"],
                "pair_display": pair_bias["display"],
                "base_state": _currency_state_text(base_row),
                "quote_state": _currency_state_text(quote_row),
                "base_strength": int(base_row["signed_strength"]),
                "quote_strength": int(quote_row["signed_strength"]),
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result["_abs_edge"] = result["pair_edge"].abs()
    return (
        result.sort_values(
            ["_abs_edge", "pair"],
            ascending=[False, True],
        )
        .drop(columns="_abs_edge")
        .reset_index(drop=True)
    )


def classify_20y_40d_seasonality(
    *,
    pair_direction: int,
    sample_size: int,
    positive_years: int,
    positive_rate: float,
    base_rate: float,
    median_return: float,
    min_years: int = FX_SEASONALITY_MIN_YEARS,
) -> dict:
    """
    Single-window FX seasonality:
    20 completed historical years, 40 trading days forward.

    Direction follows the project's existing seasonality rule:
      bullish = median > 0 AND positive rate > pair base rate
      bearish = median < 0 AND positive rate < pair base rate
      otherwise mixed
    """
    n = int(sample_size or 0)
    k = int(positive_years or 0)

    finite = all(
        np.isfinite(float(v))
        for v in (positive_rate, base_rate, median_return)
    )

    if n < int(min_years) or not finite:
        return {
            "seasonal_direction": 0,
            "seasonal_label": "N/V",
            "support": "N/V",
            "support_display": "— N/V",
            "supports": False,
        }

    if float(median_return) > 0 and float(positive_rate) > float(base_rate):
        seasonal_direction = 1
        seasonal_label = "BULLISH"
    elif float(median_return) < 0 and float(positive_rate) < float(base_rate):
        seasonal_direction = -1
        seasonal_label = "BÄRISCH"
    else:
        seasonal_direction = 0
        seasonal_label = "GEMISCHT"

    if int(pair_direction) == 0:
        support = "NEUTRAL"
        support_display = "— NEUTRAL"
        supports = False
    elif seasonal_direction == 0:
        support = "GEMISCHT"
        support_display = "— GEMISCHT"
        supports = False
    elif seasonal_direction == int(pair_direction):
        support = "UNTERSTÜTZT"
        support_display = "✓ UNTERSTÜTZT"
        supports = True
    else:
        support = "GEGENLÄUFIG"
        support_display = "✕ GEGENLÄUFIG"
        supports = False

    return {
        "seasonal_direction": seasonal_direction,
        "seasonal_label": seasonal_label,
        "support": support,
        "support_display": support_display,
        "supports": supports,
        "detail": (
            f"{k}/{n} positiv · Median {float(median_return):+.2%} · "
            f"Basisrate {float(base_rate):.0%}"
        ),
    }



def summarize_fx_horizons(results: dict[int, dict]) -> dict:
    compact=[]; valid=[]; details=[]
    for h in (20,40,60):
        r=results.get(h,{})
        support=r.get('support','N/V')
        if support=='UNTERSTÜTZT': mark='✓'; valid.append(3)
        elif support=='GEGENLÄUFIG': mark='✕'; valid.append(1)
        elif support in {'GEMISCHT','NEUTRAL'}: mark='—'; valid.append(2)
        else: mark='·'
        compact.append(f"{h}{mark}")
        if r.get('detail'): details.append(f"{h}T: {r['detail']}")
    if not valid: rank=0; overall='N/V'
    elif all(v==3 for v in valid): rank=4; overall='STABIL UNTERSTÜTZT'
    elif 3 in valid and 1 not in valid: rank=3; overall='ÜBERWIEGEND UNTERSTÜTZT'
    elif all(v==1 for v in valid): rank=1; overall='GEGENLÄUFIG'
    else: rank=2; overall='GEMISCHT'
    return {'compact':' · '.join(compact),'overall':overall,'overall_rank':rank,'detail':' | '.join(details)}

def summarize_currency_horizons(results: dict[int, dict]) -> dict:
    """Compact 20/40/60T directional view for a single currency.

    The arrows show the seasonal direction itself, not a new COT score:
      ▲ bullish seasonality
      ▼ bearish seasonality
      — mixed / no clear seasonal direction
      · insufficient history

    ``supported_horizons`` is kept separately for research/UI context.
    """
    compact = []
    details = []
    valid_horizons = 0
    supported_horizons = 0

    for horizon in (20, 40, 60):
        result = results.get(horizon, {})
        support = str(result.get("support", "N/V"))

        if support == "N/V":
            mark = "·"
        else:
            valid_horizons += 1
            direction = int(result.get("seasonal_direction", 0) or 0)
            mark = "▲" if direction > 0 else "▼" if direction < 0 else "—"
            if support == "UNTERSTÜTZT":
                supported_horizons += 1

        compact.append(f"{horizon}{mark}")
        if result.get("detail"):
            details.append(f"{horizon}T: {result['detail']}")

    return {
        "compact": " · ".join(compact),
        "valid_horizons": valid_horizons,
        "supported_horizons": supported_horizons,
        "detail": " | ".join(details) if details else "Keine ausreichende Historie",
    }
