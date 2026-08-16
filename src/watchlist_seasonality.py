from __future__ import annotations

import pandas as pd
import streamlit as st

from .prices import load_prices
from .seasonality import forward_statistics
from .watchlist_seasonality_core import (
    FORWARD_DAYS,
    HISTORY_YEARS,
    classify_asset_seasonality,
    summarize_multi_horizon,
)


def _empty_results(detail: str) -> dict:
    results = {
        h: {
            "support": "N/V",
            "display": "— N/V",
            "supports": False,
            "detail": detail,
        }
        for h in FORWARD_DAYS
    }
    return {"horizons": results, **summarize_multi_horizon(results)}


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def calculate_market_20y_multi_seasonality(
    ticker: str,
    cot_direction: int,
) -> dict:
    """20 completed years, evaluated at 20/40/60 trading days forward."""
    ticker = str(ticker or "").strip()
    if not ticker:
        return _empty_results("Kein Preis-Ticker hinterlegt")

    try:
        prices = load_prices(ticker, start="1990-01-01")
    except Exception as exc:
        return _empty_results(f"Preisfeed nicht verfügbar: {exc}")

    if prices is None or prices.empty:
        return _empty_results("Keine Preishistorie")

    stats = forward_statistics(
        prices,
        history_windows=(HISTORY_YEARS,),
        horizons=tuple(FORWARD_DAYS),
    )

    results = {}
    for horizon in FORWARD_DAYS:
        rows = stats[
            (stats["historie_jahre"] == HISTORY_YEARS)
            & (stats["horizont_tage"] == horizon)
        ] if stats is not None and not stats.empty else pd.DataFrame()

        if rows.empty:
            results[horizon] = {
                "support": "N/V",
                "display": "— N/V",
                "supports": False,
                "detail": "Keine ausreichende 20J-Historie",
            }
            continue

        row = rows.iloc[0]
        result = classify_asset_seasonality(
            cot_direction=int(cot_direction),
            sample_size=int(row["stichprobe"]),
            positive_years=int(row["positive_jahre"]),
            positive_rate=float(row["trefferquote_positiv"]),
            base_rate=float(row["basisrate_positiv"]),
            median_return=float(row["median_rendite"]),
        )
        result.update({
            "sample_size": int(row["stichprobe"]),
            "positive_years": int(row["positive_jahre"]),
            "positive_rate": float(row["trefferquote_positiv"]),
            "base_rate": float(row["basisrate_positiv"]),
            "median_return": float(row["median_rendite"]),
            "binomial_p": float(row["binomial_p"]),
        })
        results[horizon] = result

    return {"horizons": results, **summarize_multi_horizon(results)}
