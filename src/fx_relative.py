from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from .analysis import enrich_cot
from .cftc import load_cftc_universe, load_history, resolve_market
from .config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
)
from .fx_relative_core import (
    CURRENCY_ORDER,
    FX_SEASONALITY_FORWARD_DAYS,
    FX_SEASONALITY_HISTORY_YEARS,
    summarize_fx_horizons,
    build_all_fx_pairs,
    classify_20y_40d_seasonality,
    currency_cot_profile,
)
from .markets import CLASSIC_MARKETS
from .seasonality import forward_statistics


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_currency_cot_profiles() -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = load_cftc_universe()
    rows = []
    errors = []

    for market in CLASSIC_MARKETS["Currencies"]:
        try:
            resolved = resolve_market(market, universe)
            if not resolved:
                raise ValueError("Keine eindeutige CFTC-Serie aufgelöst")

            code = str(resolved["cftc_contract_market_code"])
            raw = load_history(code)
            if raw.empty:
                raise ValueError("Keine COT-Historie")

            cot = enrich_cot(
                raw,
                weeks=COT_INDEX_WEEKS,
                validation_weeks=NET_VALIDATION_WEEKS,
                range_weeks=COMMERCIAL_RANGE_WEEKS,
            )

            valid = cot.dropna(
                subset=[
                    "commercial_index",
                    "commercial_net_percentile",
                    "noncommercial_net_percentile",
                    "retail_net_percentile",
                ]
            )
            if valid.empty:
                raise ValueError(
                    "Nicht genügend Historie für COT- und Netto-Einordnung"
                )

            latest = valid.iloc[-1]
            profile = currency_cot_profile(
                symbol=market["symbol"],
                market_name=market["name"],
                report_date=latest["report_date"],
                commercial_index=latest["commercial_index"],
                commercial_net_percentile=latest[
                    "commercial_net_percentile"
                ],
                noncommercial_net_percentile=latest[
                    "noncommercial_net_percentile"
                ],
                retail_net_percentile=latest["retail_net_percentile"],
                index_upper=INDEX_UPPER,
                index_lower=INDEX_LOWER,
                net_upper=NET_UPPER_PERCENTILE,
                net_lower=NET_LOWER_PERCENTILE,
            )
            profile["cftc_code"] = code
            rows.append(profile)

        except Exception as exc:
            errors.append(
                {
                    "symbol": market["symbol"],
                    "market_name": market["name"],
                    "error": str(exc),
                }
            )

    profiles = pd.DataFrame(rows)
    if not profiles.empty:
        profiles = profiles[
            profiles["symbol"].isin(CURRENCY_ORDER)
        ].copy()

        order = {symbol: idx for idx, symbol in enumerate(CURRENCY_ORDER)}
        profiles["_order"] = profiles["symbol"].map(order)
        profiles = (
            profiles.sort_values("_order")
            .drop(columns="_order")
            .reset_index(drop=True)
        )

    errors_df = pd.DataFrame(errors)
    if not errors_df.empty:
        errors_df = errors_df[
            errors_df["symbol"].isin(CURRENCY_ORDER)
        ].reset_index(drop=True)

    return profiles, errors_df


def _extract_close(raw: pd.DataFrame, ticker: str) -> pd.Series:
    if raw is None or raw.empty:
        return pd.Series(dtype=float)

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(map(str, raw.columns.get_level_values(0)))
        level1 = set(map(str, raw.columns.get_level_values(1)))

        try:
            if ticker in level0:
                part = raw[ticker]
                field = "Adj Close" if "Adj Close" in part.columns else "Close"
                if field in part.columns:
                    return pd.to_numeric(part[field], errors="coerce").dropna()

            if ticker in level1:
                for field in ("Adj Close", "Close"):
                    if field in level0:
                        return pd.to_numeric(
                            raw[(field, ticker)],
                            errors="coerce",
                        ).dropna()
        except Exception:
            return pd.Series(dtype=float)

        return pd.Series(dtype=float)

    field = "Adj Close" if "Adj Close" in raw.columns else "Close"
    if field not in raw.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(raw[field], errors="coerce").dropna()


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def load_currency_usd_values(
    start: str = "2000-01-01",
) -> dict[str, pd.DataFrame]:
    """
    Build each currency's historical value in USD.

    For each non-USD currency both direct and inverse Yahoo spot-FX quotes are
    requested. Direct quotes are preferred; inverse quotes are inverted.
    """
    non_usd = [currency for currency in CURRENCY_ORDER if currency != "USD"]

    tickers = []
    for currency in non_usd:
        tickers.extend(
            [
                f"{currency}USD=X",
                f"USD{currency}=X",
            ]
        )

    try:
        raw = yf.download(
            tickers=tickers,
            start=start,
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
            group_by="ticker",
        )
    except Exception:
        return {}

    result: dict[str, pd.DataFrame] = {}

    for currency in non_usd:
        direct = _extract_close(raw, f"{currency}USD=X")
        inverse = _extract_close(raw, f"USD{currency}=X")

        if not direct.empty:
            values = direct.copy()
        elif not inverse.empty:
            inverse = inverse[inverse > 0]
            values = 1.0 / inverse
        else:
            continue

        values.index = pd.to_datetime(values.index)
        if getattr(values.index, "tz", None) is not None:
            values.index = values.index.tz_localize(None)

        result[currency] = (
            pd.DataFrame(
                {"close": pd.to_numeric(values, errors="coerce")}
            )
            .dropna()
            .sort_index()
        )

    # USD is exactly 1 USD in USD. Use the combined FX calendar so crosses
    # involving USD align with the same historical trading dates.
    if result:
        all_dates = sorted(
            set().union(
                *[set(frame.index) for frame in result.values()]
            )
        )
        if all_dates:
            result["USD"] = pd.DataFrame(
                {"close": np.ones(len(all_dates), dtype=float)},
                index=pd.DatetimeIndex(all_dates),
            )

    return result


def synthesize_pair_prices(
    base: str,
    quote: str,
    values: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Construct the actual Base/Quote price relationship.

    If V_base and V_quote are both expressed in USD:
        Base/Quote = V_base / V_quote
    """
    if base not in values or quote not in values:
        return pd.DataFrame()

    base_values = values[base][["close"]].rename(
        columns={"close": "base"}
    )
    quote_values = values[quote][["close"]].rename(
        columns={"close": "quote"}
    )

    joined = base_values.join(quote_values, how="inner").dropna()
    joined = joined[
        (joined["base"] > 0)
        & (joined["quote"] > 0)
    ]

    if joined.empty:
        return pd.DataFrame()

    return pd.DataFrame(
        {"close": joined["base"] / joined["quote"]},
        index=joined.index,
    )


@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def add_20y_multi_pair_seasonality(
    pairs: pd.DataFrame,
) -> pd.DataFrame:
    if pairs is None or pairs.empty:
        return pairs.copy() if pairs is not None else pd.DataFrame()

    values = load_currency_usd_values()
    output = []

    for _, row in pairs.iterrows():
        prices = synthesize_pair_prices(
            str(row["base"]),
            str(row["quote"]),
            values,
        )

        if not prices.empty:
            stats = forward_statistics(
                prices,
                history_windows=(FX_SEASONALITY_HISTORY_YEARS,),
                horizons=tuple(FX_SEASONALITY_FORWARD_DAYS),
            )
        else:
            stats = pd.DataFrame()

        horizon_results = {}
        for horizon in FX_SEASONALITY_FORWARD_DAYS:
            rows = stats[
                (stats["historie_jahre"] == FX_SEASONALITY_HISTORY_YEARS)
                & (stats["horizont_tage"] == horizon)
            ] if not stats.empty else pd.DataFrame()

            if rows.empty:
                horizon_results[horizon] = {
                    "support": "N/V",
                    "supports": False,
                    "detail": "Keine ausreichende 20J-Paarpreishistorie",
                }
                continue

            r = rows.iloc[0]
            seasonal = classify_20y_40d_seasonality(
                pair_direction=int(row["pair_direction"]),
                sample_size=int(r["stichprobe"]),
                positive_years=int(r["positive_jahre"]),
                positive_rate=float(r["trefferquote_positiv"]),
                base_rate=float(r["basisrate_positiv"]),
                median_return=float(r["median_rendite"]),
            )
            horizon_results[horizon] = seasonal

        summary = summarize_fx_horizons(horizon_results)
        item = row.to_dict()
        item.update({
            "seasonality_compact": summary["compact"],
            "seasonality_overall": summary["overall"],
            "seasonality_overall_rank": summary["overall_rank"],
            "seasonality_supports": summary["overall_rank"] >= 3,
            "seasonality_detail": summary["detail"],
        })
        output.append(item)

    return pd.DataFrame(output)


__all__ = [
    "build_all_fx_pairs",
    "load_currency_cot_profiles",
    "add_20y_multi_pair_seasonality",
]

