from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_prices(ticker: str, start) -> pd.DataFrame:
    """Load daily closes.

    No weekly resampling is performed here. COT alignment is done explicitly by
    ``align_prices_to_cot`` so the selected close can never come from after the
    Tuesday COT report date.
    """
    if not ticker:
        return pd.DataFrame()

    try:
        df = yf.download(
            ticker,
            start=pd.Timestamp(start) - pd.Timedelta(days=14),
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    close_col = "Adj Close" if "Adj Close" in df.columns else "Close"
    if close_col not in df.columns:
        return pd.DataFrame()

    out = df[[close_col]].rename(columns={close_col: "close"}).copy()
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    return out.dropna().sort_index()


def _same_iso_week(a, b) -> bool:
    if pd.isna(a) or pd.isna(b):
        return False
    aa = pd.Timestamp(a)
    bb = pd.Timestamp(b)
    ia = aa.isocalendar()
    ib = bb.isocalendar()
    return int(ia.year) == int(ib.year) and int(ia.week) == int(ib.week)


def align_prices_to_cot(
    cot: pd.DataFrame,
    prices: pd.DataFrame,
    report_date_col: str = "report_date",
) -> pd.DataFrame:
    """Attach the last available daily close on or before each COT report date.

    The COT report date is normally Tuesday. This function does not resample to
    Friday or any other weekly close. It stores the exact price date and an
    explicit alignment flag. A valid observation must satisfy both:

    1. price_date <= report_date
    2. price_date and report_date are in the same ISO week

    If the current COT week has no eligible price observation, the price remains
    attached for auditability but ``cot_price_alignment_ok`` is False; downstream
    divergence calculations invalidate that observation instead of silently
    using a prior week's close.
    """
    out = cot.copy()
    out["cot_price"] = np.nan
    out["cot_price_date"] = pd.NaT
    out["cot_price_alignment_ok"] = False
    out["cot_report_weekday"] = pd.to_datetime(
        out.get(report_date_col), errors="coerce"
    ).dt.day_name()

    if prices is None or prices.empty or "close" not in prices.columns:
        return out

    p = prices[["close"]].copy().dropna().sort_index()
    p.index = pd.to_datetime(p.index)
    if getattr(p.index, "tz", None) is not None:
        p.index = p.index.tz_localize(None)

    idx = p.index
    selected_prices = []
    selected_dates = []
    alignment = []

    for ts in pd.to_datetime(out[report_date_col], errors="coerce"):
        if pd.isna(ts):
            selected_prices.append(np.nan)
            selected_dates.append(pd.NaT)
            alignment.append(False)
            continue

        report_ts = pd.Timestamp(ts)
        pos = idx.searchsorted(report_ts, side="right") - 1
        if pos < 0:
            selected_prices.append(np.nan)
            selected_dates.append(pd.NaT)
            alignment.append(False)
            continue

        price_date = pd.Timestamp(idx[pos])
        price_value = float(p.iloc[pos]["close"])
        ok = bool(price_date <= report_ts and _same_iso_week(price_date, report_ts))

        # Keep the selected source date for auditability, but do not expose an
        # invalid prior-week price as a usable COT price.
        selected_prices.append(price_value if ok else np.nan)
        selected_dates.append(price_date)
        alignment.append(ok)

    out["cot_price"] = selected_prices
    out["cot_price_date"] = pd.to_datetime(selected_dates)
    out["cot_price_alignment_ok"] = alignment
    return out


def price_alignment_audit(aligned: pd.DataFrame) -> dict:
    """Compact audit information for UI/tests."""
    if aligned is None or aligned.empty:
        return {
            "n": 0,
            "valid": 0,
            "invalid": 0,
            "future_prices": 0,
            "report_weekdays": {},
        }

    report = pd.to_datetime(aligned.get("report_date"), errors="coerce")
    price = pd.to_datetime(aligned.get("cot_price_date"), errors="coerce")
    valid = aligned.get(
        "cot_price_alignment_ok",
        pd.Series(False, index=aligned.index),
    ).fillna(False).astype(bool)

    future = (price > report).fillna(False)
    weekdays = report.dt.day_name().value_counts(dropna=False).to_dict()
    return {
        "n": int(len(aligned)),
        "valid": int(valid.sum()),
        "invalid": int((~valid).sum()),
        "future_prices": int(future.sum()),
        "report_weekdays": weekdays,
    }
