from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

from .analysis import rolling_percentile
from .cftc_reports import load_report_history, primary_report_for_asset_class
from .prices import load_prices


PERCENTILE_WEEKS = 156


@dataclass(frozen=True)
class GroupSpec:
    institutional_key: str
    institutional_label: str
    trend_key: str
    trend_label: str
    nonreportable_key: str = "nonreportable"


def group_spec_for_asset_class(asset_class: str) -> GroupSpec:
    report_type = primary_report_for_asset_class(str(asset_class))
    if report_type == "tff":
        return GroupSpec(
            institutional_key="asset_manager",
            institutional_label="Asset Manager",
            trend_key="leveraged_funds",
            trend_label="Leveraged Funds",
        )
    if report_type == "disaggregated":
        return GroupSpec(
            institutional_key="producer",
            institutional_label="Producer / Merchant",
            trend_key="managed_money",
            trend_label="Managed Money",
        )
    return GroupSpec(
        institutional_key="nonreportable",
        institutional_label="—",
        trend_key="nonreportable",
        trend_label="—",
    )


def _finite(value, default=np.nan) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(default)
    return value if np.isfinite(value) else float(default)


def enrich_report_group_percentiles(
    history: pd.DataFrame,
    *,
    weeks: int = PERCENTILE_WEEKS,
) -> pd.DataFrame:
    """Add 156W net-position percentiles and 1/2/4W transitions per CFTC group."""
    if history is None or history.empty:
        return pd.DataFrame()
    out = history.copy()
    long_cols = [c for c in out.columns if c.endswith("_long")]
    groups = [c[:-5] for c in long_cols if f"{c[:-5]}_short" in out.columns]
    for group in groups:
        net_col = f"{group}_net"
        pct_col = f"{group}_net_percentile_156w"
        out[net_col] = pd.to_numeric(out[f"{group}_long"], errors="coerce") - pd.to_numeric(
            out[f"{group}_short"], errors="coerce"
        )
        out[pct_col] = rolling_percentile(out[net_col], int(weeks))
        for lag in (1, 2, 4):
            out[f"{group}_pct_delta_{lag}w"] = out[pct_col].diff(lag)
    return out


def classify_group_transition(
    *,
    percentile: float,
    delta_1w: float,
    delta_2w: float,
    delta_4w: float,
    expected_direction: int,
) -> dict:
    """Describe whether a group is starting to move with the prospective reversal.

    The function intentionally describes *motion*, not a trade signal. For a
    prospective bullish reversal, rising net-percentiles are aligned; for a
    prospective bearish reversal, falling percentiles are aligned.
    """
    pct = _finite(percentile)
    deltas = [_finite(delta_1w), _finite(delta_2w), _finite(delta_4w)]
    direction = int(np.sign(expected_direction))
    if direction == 0 or not np.isfinite(pct):
        return {
            "label": "KEIN KONTEXT",
            "tone": "neutral",
            "aligned": False,
            "strong": False,
            "score": 0.0,
        }

    available = [d for d in deltas if np.isfinite(d)]
    if not available:
        return {
            "label": "N/V",
            "tone": "neutral",
            "aligned": False,
            "strong": False,
            "score": 0.0,
        }

    d1, d2, d4 = deltas
    weighted = 0.0
    weight_sum = 0.0
    for d, w in ((d1, 1.0), (d2, 1.5), (d4, 2.5)):
        if np.isfinite(d):
            weighted += direction * d * w
            weight_sum += w
    score = weighted / weight_sum if weight_sum else 0.0
    aligned_votes = sum(1 for d in available if direction * d > 0.75)
    against_votes = sum(1 for d in available if direction * d < -0.75)
    favorable_side = (direction > 0 and pct >= 50.0) or (direction < 0 and pct <= 50.0)

    if score >= 7.5 and aligned_votes >= 2:
        label = "DREHT" if favorable_side else "TRENDABBAU"
        tone = "good"
    elif score >= 3.0 and aligned_votes >= 2:
        label = "DREHT" if favorable_side else "VERLANGSAMT"
        tone = "good"
    elif score >= 1.0 and aligned_votes >= 1:
        label = "VERLANGSAMT"
        tone = "warn"
    elif score <= -3.0 and against_votes >= 2:
        label = "GEGENLÄUFIG"
        tone = "bad"
    else:
        label = "SEITWÄRTS"
        tone = "neutral"

    return {
        "label": label,
        "tone": tone,
        "aligned": bool(score >= 3.0 and aligned_votes >= 2),
        "strong": bool(score >= 7.5 and aligned_votes >= 2),
        "score": float(score),
        "favorable_side": bool(favorable_side),
    }


def classify_nonreportable_context(percentile: float, expected_direction: int) -> dict:
    pct = _finite(percentile)
    direction = int(np.sign(expected_direction))
    if direction == 0 or not np.isfinite(pct):
        return {"label": "N/V", "tone": "neutral", "contrarian": False, "strong": False}
    if direction > 0:
        if pct <= 20:
            return {"label": "FALSCHE SEITE", "tone": "bad", "contrarian": True, "strong": True}
        if pct <= 35:
            return {"label": "KONTRÄR", "tone": "warn", "contrarian": True, "strong": False}
    else:
        if pct >= 80:
            return {"label": "FALSCHE SEITE", "tone": "bad", "contrarian": True, "strong": True}
        if pct >= 65:
            return {"label": "KONTRÄR", "tone": "warn", "contrarian": True, "strong": False}
    return {"label": "GEMISCHT", "tone": "neutral", "contrarian": False, "strong": False}


def _group_snapshot(row: pd.Series, key: str, expected_direction: int) -> dict:
    pct = _finite(row.get(f"{key}_net_percentile_156w"))
    d1 = _finite(row.get(f"{key}_pct_delta_1w"))
    d2 = _finite(row.get(f"{key}_pct_delta_2w"))
    d4 = _finite(row.get(f"{key}_pct_delta_4w"))
    motion = classify_group_transition(
        percentile=pct,
        delta_1w=d1,
        delta_2w=d2,
        delta_4w=d4,
        expected_direction=expected_direction,
    )
    return {
        "percentile": pct,
        "delta_1w": d1,
        "delta_2w": d2,
        "delta_4w": d4,
        **motion,
    }


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_cross_group_context(
    asset_class: str,
    contract_code: str,
    expected_direction: int,
) -> dict:
    """Load the detailed CFTC report and describe its participant transitions."""
    report_type = primary_report_for_asset_class(str(asset_class))
    spec = group_spec_for_asset_class(str(asset_class))
    try:
        raw = load_report_history(report_type, str(contract_code))
    except Exception as exc:
        return {
            "report_type": report_type,
            "institutional_label": spec.institutional_label,
            "trend_label": spec.trend_label,
            "error": str(exc),
        }
    enriched = enrich_report_group_percentiles(raw)
    if enriched.empty:
        return {
            "report_type": report_type,
            "institutional_label": spec.institutional_label,
            "trend_label": spec.trend_label,
            "error": "Keine Detailhistorie",
        }
    valid = enriched.dropna(subset=[f"{spec.nonreportable_key}_net_percentile_156w"])
    if valid.empty:
        return {
            "report_type": report_type,
            "institutional_label": spec.institutional_label,
            "trend_label": spec.trend_label,
            "error": "Nicht genügend 156W-Historie",
        }
    latest = valid.iloc[-1]
    inst = _group_snapshot(latest, spec.institutional_key, expected_direction)
    trend = _group_snapshot(latest, spec.trend_key, expected_direction)
    nr_pct = _finite(latest.get(f"{spec.nonreportable_key}_net_percentile_156w"))
    nr = classify_nonreportable_context(nr_pct, expected_direction)
    return {
        "report_type": report_type,
        "report_date": latest.get("report_date"),
        "institutional_label": spec.institutional_label,
        "institutional": inst,
        "trend_label": spec.trend_label,
        "trend": trend,
        "nonreportable_percentile": nr_pct,
        "nonreportable": nr,
        "error": None,
    }


def classify_price_structure(prices: pd.DataFrame, expected_direction: int) -> dict:
    """Lightweight price confirmation context; never a COT signal by itself."""
    direction = int(np.sign(expected_direction))
    if direction == 0 or prices is None or prices.empty or "close" not in prices.columns:
        return {"label": "N/V", "tone": "neutral", "confirming": False, "ret20": np.nan, "ret60": np.nan}
    close = pd.to_numeric(prices["close"], errors="coerce").dropna()
    if len(close) < 65:
        return {"label": "N/V", "tone": "neutral", "confirming": False, "ret20": np.nan, "ret60": np.nan}
    current = float(close.iloc[-1])
    ret20 = current / float(close.iloc[-21]) - 1.0
    ret60 = current / float(close.iloc[-61]) - 1.0
    prior20 = close.iloc[-21:-1]
    breakout = bool(current > float(prior20.max())) if direction > 0 else bool(current < float(prior20.min()))
    aligned20 = direction * ret20
    aligned60 = direction * ret60

    if breakout:
        label, tone, confirming = ("STRUCTURE BREAK ↑", "good", True) if direction > 0 else ("STRUCTURE BREAK ↓", "good", True)
    elif aligned20 >= 0.015 and aligned20 > aligned60:
        label, tone, confirming = ("TURNING ↑", "good", True) if direction > 0 else ("TURNING ↓", "good", True)
    elif aligned20 > aligned60 + 0.02:
        label, tone, confirming = "STALLING", "warn", False
    else:
        label, tone, confirming = "NO CONFIRM", "neutral", False
    return {
        "label": label,
        "tone": tone,
        "confirming": confirming,
        "ret20": float(ret20),
        "ret60": float(ret60),
    }


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_price_structure(ticker: str, expected_direction: int) -> dict:
    ticker = str(ticker or "").strip()
    if not ticker:
        return {"label": "N/V", "tone": "neutral", "confirming": False, "ret20": np.nan, "ret60": np.nan}
    try:
        prices = load_prices(ticker, start="1990-01-01")
    except Exception:
        prices = pd.DataFrame()
    return classify_price_structure(prices, expected_direction)


def classify_regime_stage(
    *,
    cycle_phase: str,
    commercial_transition: str,
    institutional: dict | None,
    trend: dict | None,
    nonreportable: dict | None,
    price: dict | None,
) -> dict:
    """Turn the divide-and-conquer pipeline into a descriptive stage (1..5).

    Stage 5 is called CONTEXT READY rather than TRADE READY because the user's
    Supply/Demand entry remains a separate manual decision in the Trade Planner.
    """
    phase = str(cycle_phase or "").upper()
    transition = str(commercial_transition or "").upper()
    inst = dict(institutional or {})
    tr = dict(trend or {})
    nr = dict(nonreportable or {})
    px = dict(price or {})

    if phase not in {"EXTREME", "RELEASE"}:
        return {"stage": 0, "label": "NORMAL", "tone": "neutral"}

    stage = 1
    label = "EXTREME WATCH"
    tone = "bad"

    commercial_transition_active = phase == "RELEASE" or "EARLY RELEASE" in transition
    if commercial_transition_active:
        stage, label, tone = 2, "IN TRANSITION", "warn"

    cross_group = bool(inst.get("aligned") or tr.get("aligned"))
    if commercial_transition_active and cross_group:
        stage, label, tone = 3, "CROSS-GROUP SHIFT", "warn"

    confirmed = bool(
        phase == "RELEASE"
        and inst.get("aligned")
        and tr.get("aligned")
        and nr.get("contrarian")
    )
    if confirmed:
        stage, label, tone = 4, "REGIME CONFIRMED", "good"

    if confirmed and px.get("confirming"):
        stage, label, tone = 5, "CONTEXT READY", "good"

    return {"stage": int(stage), "label": label, "tone": tone}
