
from __future__ import annotations

import re
import pandas as pd
import requests
import streamlit as st

from .markets import EXCLUDE_TERMS

DATASETS = {
    "legacy": {
        "id": "6dca-aqww",
        "label": "Legacy · Futures Only",
    },
    "disaggregated": {
        "id": "72hh-3qpy",
        "label": "Disaggregated · Futures Only",
    },
    "tff": {
        "id": "gpe5-46if",
        "label": "TFF · Futures Only",
    },
}

COMMODITY_CLASSES = {
    "Energy", "Metals", "Grains", "Livestock", "Soft Commodities",
    "Forest Products"
}
FINANCIAL_CLASSES = {"Currencies", "Cryptocurrencies", "Rates", "Volatility", "Indices"}


def primary_report_for_asset_class(asset_class: str) -> str:
    if asset_class in COMMODITY_CLASSES:
        return "disaggregated"
    if asset_class in FINANCIAL_CLASSES:
        return "tff"
    return "legacy"


def _api(report_type: str) -> str:
    dataset = DATASETS[report_type]["id"]
    return f"https://publicreporting.cftc.gov/resource/{dataset}.json"


def _request(report_type: str, params: dict) -> list[dict]:
    response = requests.get(
        _api(report_type),
        params=params,
        timeout=35,
        headers={"User-Agent": "COT-Research-V3/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _normalize(value: str) -> str:
    value = str(value).upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_report_universe(report_type: str) -> pd.DataFrame:
    params = {
        "$select": ",".join([
            "market_and_exchange_names",
            "cftc_contract_market_code",
            "commodity_name",
            "max(report_date_as_yyyy_mm_dd) as latest_date",
        ]),
        "$group": ",".join([
            "market_and_exchange_names",
            "cftc_contract_market_code",
            "commodity_name",
        ]),
        "$limit": 50000,
    }
    rows = _request(report_type, params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for col in (
        "market_and_exchange_names",
        "commodity_name",
        "cftc_contract_market_code",
    ):
        df[col] = df.get(col, "").fillna("").astype(str)

    df["latest_date"] = pd.to_datetime(
        df.get("latest_date"), errors="coerce", utc=True
    ).dt.tz_localize(None)
    return df


def resolve_report_market(config: dict, universe: pd.DataFrame) -> dict | None:
    if universe.empty:
        return None

    latest_global = universe["latest_date"].max()
    aliases = [_normalize(a) for a in config["aliases"]]
    target_exchange = _normalize(config.get("exchange", ""))
    target_contract_code = str(config.get("cftc_code", "")).strip()
    allowed_excluded_terms = {
        _normalize(term)
        for term in config.get("allow_excluded_terms", [])
    }

    best = None
    best_score = float("-inf")

    for row in universe.to_dict("records"):
        commodity_raw = row.get("commodity_name", "")
        market_raw = row.get("market_and_exchange_names", "")
        commodity = _normalize(commodity_raw)
        market_text = _normalize(market_raw)
        combined = _normalize(f"{commodity_raw} {market_raw}")

        row_contract_code = str(row.get("cftc_contract_market_code", "")).strip()
        if target_contract_code and row_contract_code == target_contract_code:
            return row

        if any(
            _normalize(term) in combined
            and _normalize(term) not in allowed_excluded_terms
            for term in EXCLUDE_TERMS
        ):
            continue

        if config.get("symbol") in {"EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "MXN", "BRL", "ZAR"}:
            if any(term in combined for term in ("XRATE", "CROSS RATE", "CROSSRATE")):
                continue

            upper_name = str(market_raw).upper()
            if (
                "/" in upper_name
                and "U.S. DOLLAR" not in upper_name
                and "US DOLLAR" not in upper_name
            ):
                continue

        exact = [a for a in aliases if a and commodity == a]
        prefix = [a for a in aliases if a and market_text.startswith(a)]
        substring = [a for a in aliases if a and a in combined]

        if exact:
            score = 300 + max(len(a.split()) for a in exact) * 10
        elif prefix:
            score = 180 + max(len(a.split()) for a in prefix) * 10
        elif substring:
            score = 80 + max(len(a.split()) for a in substring) * 10
        else:
            continue

        if target_exchange and target_exchange in combined:
            score += 40

        latest = row.get("latest_date")
        if pd.notna(latest) and pd.notna(latest_global):
            age = (latest_global - latest).days
            if age <= 21:
                score += 30
            elif age <= 90:
                score += 10
            else:
                score -= min(age / 30, 50)

        for term in (
            "XRATE", "CROSS RATE", "CROSSRATE", "E MINI",
            "MICRO", "SPREAD", "BASIS", "SWAP"
        ):
            if term in combined and term not in _normalize(config["name"]):
                score -= 100

        if score > best_score:
            best_score = score
            best = row

    return best


COMMON_FIELDS = [
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "commodity_name",
    "cftc_contract_market_code",
    "open_interest_all",
]

REPORT_FIELDS = {
    "disaggregated": {
        "producer_long": "prod_merc_positions_long",
        "producer_short": "prod_merc_positions_short",
        "swap_long": "swap_positions_long_all",
        "swap_short": "swap__positions_short_all",
        "managed_money_long": "m_money_positions_long_all",
        "managed_money_short": "m_money_positions_short_all",
        "other_reportable_long": "other_rept_positions_long",
        "other_reportable_short": "other_rept_positions_short",
        "nonreportable_long": "nonrept_positions_long_all",
        "nonreportable_short": "nonrept_positions_short_all",
    },
    "tff": {
        "dealer_long": "dealer_positions_long_all",
        "dealer_short": "dealer_positions_short_all",
        "asset_manager_long": "asset_mgr_positions_long",
        "asset_manager_short": "asset_mgr_positions_short",
        "leveraged_funds_long": "lev_money_positions_long",
        "leveraged_funds_short": "lev_money_positions_short",
        "other_reportable_long": "other_rept_positions_long",
        "other_reportable_short": "other_rept_positions_short",
        "nonreportable_long": "nonrept_positions_long_all",
        "nonreportable_short": "nonrept_positions_short_all",
    },
}


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_report_history(report_type: str, contract_code: str) -> pd.DataFrame:
    if report_type not in REPORT_FIELDS:
        raise ValueError(f"Unsupported report type: {report_type}")

    safe_code = str(contract_code).replace("'", "''")
    raw_fields = list(REPORT_FIELDS[report_type].values())
    params = {
        "$select": ",".join(COMMON_FIELDS + raw_fields),
        "$where": f"cftc_contract_market_code='{safe_code}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": 50000,
    }

    rows = _request(report_type, params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    rename = {"report_date_as_yyyy_mm_dd": "report_date"}
    rename.update({v: k for k, v in REPORT_FIELDS[report_type].items()})
    df = df.rename(columns=rename)

    df["report_date"] = pd.to_datetime(
        df["report_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    numeric = ["open_interest_all"] + list(REPORT_FIELDS[report_type].keys())
    for col in numeric:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")

    return (
        df.dropna(subset=["report_date"])
        .sort_values("report_date")
        .drop_duplicates("report_date", keep="last")
        .reset_index(drop=True)
    )
