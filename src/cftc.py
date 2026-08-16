
from __future__ import annotations

import re
import pandas as pd
import requests
import streamlit as st

from .markets import EXCLUDE_TERMS

API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

def _request(params: dict) -> list[dict]:
    response = requests.get(
        API,
        params=params,
        timeout=35,
        headers={"User-Agent": "COT-Classic-Research/1.0"},
    )
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_cftc_universe() -> pd.DataFrame:
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
    rows = _request(params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ("market_and_exchange_names", "commodity_name", "cftc_contract_market_code"):
        df[col] = df.get(col, "").fillna("").astype(str)
    df["latest_date"] = pd.to_datetime(df.get("latest_date"), errors="coerce", utc=True).dt.tz_localize(None)
    return df

def _normalize(value: str) -> str:
    value = str(value).upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def resolve_market(config: dict, universe: pd.DataFrame) -> dict | None:
    """
    Resolve a classic market to the official Legacy Futures Only series.

    Exact commodity-name matches are preferred strongly. This prevents
    contracts such as EURO FX/JAPANESE YEN XRATE from being selected when
    the requested market is the outright JAPANESE YEN future.
    """
    if universe.empty:
        return None

    latest_global = universe["latest_date"].max()
    best = None
    best_score = float("-inf")

    aliases = [_normalize(a) for a in config["aliases"]]
    target_exchange = _normalize(config.get("exchange", ""))
    target_contract_code = str(config.get("cftc_code", "")).strip()
    allowed_excluded_terms = {
        _normalize(term)
        for term in config.get("allow_excluded_terms", [])
    }

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

        # Classic outright FX contracts must never resolve to cross-rate series.
        if config.get("symbol") in {"EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "MXN", "BRL", "ZAR"}:
            cross_terms = ("XRATE", "CROSS RATE", "CROSSRATE")
            if any(term in str(commodity_raw).upper() or term in str(market_raw).upper()
                   for term in cross_terms):
                continue

            # Slash-based FX crosses are also rejected.
            upper_name = str(market_raw).upper()
            if "/" in upper_name and "U.S. DOLLAR" not in upper_name and "US DOLLAR" not in upper_name:
                continue

        score = float("-inf")

        # 1) Exact commodity name: by far the preferred match.
        exact_aliases = [a for a in aliases if a and commodity == a]
        if exact_aliases:
            score = 300 + max(len(a.split()) for a in exact_aliases) * 10
        else:
            # 2) Exact beginning of the official market name.
            prefix_aliases = [a for a in aliases if a and market_text.startswith(a)]
            if prefix_aliases:
                score = 180 + max(len(a.split()) for a in prefix_aliases) * 10
            else:
                # 3) Fallback substring match for naming variations.
                substring_aliases = [a for a in aliases if a and a in combined]
                if not substring_aliases:
                    continue
                score = 80 + max(len(a.split()) for a in substring_aliases) * 10

        if target_exchange and target_exchange in combined:
            score += 40

        # Prefer active/current series.
        latest = row.get("latest_date")
        if pd.notna(latest) and pd.notna(latest_global):
            age = (latest_global - latest).days
            if age <= 21:
                score += 30
            elif age <= 90:
                score += 10
            else:
                score -= min(age / 30, 50)

        # Penalise obvious non-outright descriptors that can still occur
        # outside the general exclusion list.
        specialist_terms = (
            "XRATE", "CROSS RATE", "CROSSRATE", "E MINI", "MICRO",
            "SPREAD", "BASIS", "SWAP",
        )
        for term in specialist_terms:
            if term in combined and term not in _normalize(config["name"]):
                score -= 100

        if score > best_score:
            best_score = score
            best = row

    return best


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_history(contract_code: str) -> pd.DataFrame:
    safe_code = str(contract_code).replace("'", "''")
    params = {
        "$select": ",".join([
            "report_date_as_yyyy_mm_dd",
            "market_and_exchange_names",
            "commodity_name",
            "cftc_contract_market_code",
            "open_interest_all",
            "noncomm_positions_long_all",
            "noncomm_positions_short_all",
            "comm_positions_long_all",
            "comm_positions_short_all",
            "nonrept_positions_long_all",
            "nonrept_positions_short_all",
        ]),
        "$where": f"cftc_contract_market_code='{safe_code}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": 50000,
    }
    rows = _request(params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.rename(columns={
        "report_date_as_yyyy_mm_dd": "report_date",
        "noncomm_positions_long_all": "noncommercial_long",
        "noncomm_positions_short_all": "noncommercial_short",
        "comm_positions_long_all": "commercial_long",
        "comm_positions_short_all": "commercial_short",
        "nonrept_positions_long_all": "retail_long",
        "nonrept_positions_short_all": "retail_short",
    })

    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce", utc=True).dt.tz_localize(None)
    number_cols = [
        "open_interest_all", "noncommercial_long", "noncommercial_short",
        "commercial_long", "commercial_short",
        "retail_long", "retail_short",
    ]
    for col in number_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return (
        df.dropna(subset=["report_date"])
          .sort_values("report_date")
          .drop_duplicates("report_date", keep="last")
          .reset_index(drop=True)
    )
