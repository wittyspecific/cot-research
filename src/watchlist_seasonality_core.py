from __future__ import annotations

import numpy as np


HISTORY_YEARS = 20
FORWARD_DAYS = (20, 40, 60)
MIN_YEARS = 8


def _finite(value) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def classify_asset_seasonality(
    *,
    cot_direction: int,
    sample_size: int,
    positive_years: int,
    positive_rate: float,
    base_rate: float,
    median_return: float,
    min_years: int = MIN_YEARS,
) -> dict:
    """
    Compare a market's 20Y / 40 trading-day seasonality with its current COT bias.

    Seasonality is deliberately NOT part of the 1/3-3/3 COT count.
    """
    n = int(sample_size or 0)
    k = int(positive_years or 0)

    if (
        n < int(min_years)
        or not _finite(positive_rate)
        or not _finite(base_rate)
        or not _finite(median_return)
    ):
        return {
            "seasonal_direction": 0,
            "seasonal_label": "N/V",
            "support": "N/V",
            "display": "— N/V",
            "supports": False,
            "sort_rank": 0,
            "detail": "Keine ausreichende 20J-Historie",
        }

    positive_rate = float(positive_rate)
    base_rate = float(base_rate)
    median_return = float(median_return)

    # Same directional rule as the existing project seasonality engine:
    # positive/negative median plus hit-rate relative to the market base rate.
    if median_return > 0 and positive_rate > base_rate:
        seasonal_direction = 1
        seasonal_label = "BULLISH"
    elif median_return < 0 and positive_rate < base_rate:
        seasonal_direction = -1
        seasonal_label = "BÄRISCH"
    else:
        seasonal_direction = 0
        seasonal_label = "GEMISCHT"

    if int(cot_direction) == 0:
        support = "NEUTRAL"
        display = "— NEUTRAL"
        supports = False
        sort_rank = 1
    elif seasonal_direction == int(cot_direction):
        support = "UNTERSTÜTZT"
        display = "✓ UNTERSTÜTZT"
        supports = True
        sort_rank = 3
    elif seasonal_direction == 0:
        support = "GEMISCHT"
        display = "— GEMISCHT"
        supports = False
        sort_rank = 2
    else:
        support = "GEGENLÄUFIG"
        display = "✕ GEGENLÄUFIG"
        supports = False
        sort_rank = 1

    return {
        "seasonal_direction": seasonal_direction,
        "seasonal_label": seasonal_label,
        "support": support,
        "display": display,
        "supports": supports,
        "sort_rank": sort_rank,
        "detail": (
            f"{k}/{n} positiv · Median {median_return:+.2%} · "
            f"Basisrate {base_rate:.0%}"
        ),
    }



def summarize_multi_horizon(results: dict[int, dict]) -> dict:
    ordered = (20, 40, 60)
    valid = [results[h] for h in ordered if h in results and results[h].get("support") != "N/V"]

    if not valid:
        overall = "N/V"
        overall_rank = 0
    else:
        supports = sum(r.get("support") == "UNTERSTÜTZT" for r in valid)
        opposes = sum(r.get("support") == "GEGENLÄUFIG" for r in valid)
        if supports == len(valid):
            overall = "STABIL UNTERSTÜTZT"
            overall_rank = 4
        elif opposes == len(valid):
            overall = "GEGENLÄUFIG"
            overall_rank = 1
        elif supports > 0 and opposes == 0:
            overall = "ÜBERWIEGEND UNTERSTÜTZT"
            overall_rank = 3
        else:
            overall = "GEMISCHT"
            overall_rank = 2

    compact=[]; details=[]
    for h in ordered:
        r=results.get(h,{})
        support=r.get('support','N/V')
        mark = '✓' if support=='UNTERSTÜTZT' else '✕' if support=='GEGENLÄUFIG' else '—' if support in {'GEMISCHT','NEUTRAL'} else '·'
        compact.append(f"{h}{mark}")
        if r.get('detail'): details.append(f"{h}T: {r['detail']}")
    return {
        'overall': overall,
        'overall_rank': overall_rank,
        'compact': ' · '.join(compact),
        'detail': ' | '.join(details) if details else 'Keine ausreichende Historie',
    }
