from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd
import streamlit as st

from .analysis import rolling_percentile
from .cftc_reports import load_report_history, primary_report_for_asset_class


# V3.13A · frozen interpretation of the completed FX research round.
#
# IMPORTANT:
# - 75/25 is a SOFT research watch region, not a replacement for the existing
#   80/20 production gate.
# - The empirically interesting dynamic family is raw Dealer velocity over
#   roughly 1–2 weeks.
# - The research verdict was HOLD because the parameter neighbourhood was not
#   broad/stable. Therefore this module adds context; it does not change risk,
#   order execution, S&D, SL or TP rules.
RESEARCH_VERSION = "V3.13A"
RESEARCH_SCOPE = "FX_TFF_DEALER"
RESEARCH_STATUS = "HOLD"
STATE_WEEKS = 156
SOFT_UPPER = 75.0
SOFT_LOWER = 25.0
HARD_UPPER_REFERENCE = 80.0
HARD_LOWER_REFERENCE = 20.0
FORWARD_EVIDENCE_WEEKS = 8
SOFT_RELEASE_ACTIVE_WEEKS = 6


def _finite(value: Any, default=np.nan) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(default)
    return value if np.isfinite(value) else float(default)


def directional_release_flow(raw_velocity: float, extreme_zone: int) -> float:
    """Orient raw flow so positive always means movement OUT of the extreme.

    Research semantics:
      upper extreme (+1): falling Dealer net is release-positive;
      lower extreme (-1): rising Dealer net is release-positive.
    """
    value = _finite(raw_velocity)
    zone = int(np.sign(extreme_zone))
    if zone == 0 or not np.isfinite(value):
        return np.nan
    return float(-zone * value)


def soft_episode_context(
    percentile: pd.Series,
    *,
    upper: float = SOFT_UPPER,
    lower: float = SOFT_LOWER,
    release_active_weeks: int = SOFT_RELEASE_ACTIVE_WEEKS,
) -> dict:
    """Return current/recent 75/25 research episode without changing hard gates."""
    pct = pd.to_numeric(percentile, errors="coerce").reset_index(drop=True)
    if pct.empty or not np.isfinite(_finite(pct.iloc[-1])):
        return {
            "active": False,
            "phase": "NONE",
            "zone": 0,
            "weeks_since_release": np.nan,
            "entry_index": None,
            "release_index": None,
        }

    arr = pct.to_numpy(dtype=float)
    zones = np.where(arr >= float(upper), 1, np.where(arr <= float(lower), -1, 0))
    last = len(zones) - 1
    current_zone = int(zones[last])

    if current_zone != 0:
        start = last
        while start > 0 and int(zones[start - 1]) == current_zone:
            start -= 1
        return {
            "active": True,
            "phase": "SOFT EXTREME",
            "zone": current_zone,
            "weeks_since_release": np.nan,
            "entry_index": int(start),
            "release_index": None,
        }

    prior = np.flatnonzero(zones[:last] != 0)
    if len(prior) == 0:
        return {
            "active": False,
            "phase": "NONE",
            "zone": 0,
            "weeks_since_release": np.nan,
            "entry_index": None,
            "release_index": None,
        }

    end = int(prior[-1])
    zone = int(zones[end])

    weeks_since_exit = int(last - end - 1)
    if weeks_since_exit > int(release_active_weeks):
        return {
            "active": False,
            "phase": "NONE",
            "zone": 0,
            "weeks_since_release": float(weeks_since_exit),
            "entry_index": None,
            "release_index": int(end + 1),
        }

    start = end
    while start > 0 and int(zones[start - 1]) == zone:
        start -= 1

    return {
        "active": True,
        "phase": "SOFT RELEASE",
        "zone": zone,
        "weeks_since_release": float(weeks_since_exit),
        "entry_index": int(start),
        "release_index": int(end + 1),
    }


def build_fx_dealer_research_context(history: pd.DataFrame) -> dict:
    """Build the frozen FX/TFF research overlay from already-loaded history."""
    if history is None or history.empty:
        return {"calibrated": True, "active": False, "error": "Keine TFF-Historie"}

    required = {"report_date", "dealer_long", "dealer_short", "open_interest_all"}
    missing = sorted(required.difference(history.columns))
    if missing:
        return {
            "calibrated": True,
            "active": False,
            "error": "Fehlende TFF-Spalten: " + ", ".join(missing),
        }

    x = history.copy().sort_values("report_date").reset_index(drop=True)
    x["dealer_net"] = (
        pd.to_numeric(x["dealer_long"], errors="coerce")
        - pd.to_numeric(x["dealer_short"], errors="coerce")
    )
    oi = pd.to_numeric(x["open_interest_all"], errors="coerce").replace(0, np.nan)
    x["dealer_net_oi"] = x["dealer_net"] / oi
    x["dealer_net_oi_pct_156w"] = rolling_percentile(
        x["dealer_net_oi"], STATE_WEEKS
    )

    valid = x.dropna(subset=["dealer_net", "dealer_net_oi_pct_156w"]).copy()
    if len(valid) < 3:
        return {
            "calibrated": True,
            "active": False,
            "error": "Nicht genügend 156W Dealer-Net/OI-Historie",
        }

    valid = valid.reset_index(drop=True)
    episode = soft_episode_context(valid["dealer_net_oi_pct_156w"])
    latest = valid.iloc[-1]

    raw_v1 = _finite(valid["dealer_net"].diff(1).iloc[-1])
    raw_v2 = _finite(valid["dealer_net"].diff(2).iloc[-1]) / 2.0
    zone = int(episode.get("zone", 0) or 0)
    oriented_v1 = directional_release_flow(raw_v1, zone)
    oriented_v2 = directional_release_flow(raw_v2, zone)

    flow_1w = bool(np.isfinite(oriented_v1) and oriented_v1 > 0)
    flow_2w = bool(np.isfinite(oriented_v2) and oriented_v2 > 0)
    if flow_1w and flow_2w:
        flow_support = "1–2W ALIGNED"
    elif flow_1w or flow_2w:
        flow_support = "MIXED"
    else:
        flow_support = "NO RELEASE FLOW"

    pct_now = _finite(latest["dealer_net_oi_pct_156w"])
    hard_extreme_reference = bool(
        np.isfinite(pct_now)
        and (pct_now >= HARD_UPPER_REFERENCE or pct_now <= HARD_LOWER_REFERENCE)
    )

    expected_direction = int(zone) if bool(episode.get("active")) else 0
    return {
        "calibrated": True,
        "scope": RESEARCH_SCOPE,
        "research_status": RESEARCH_STATUS,
        "active": bool(episode.get("active", False)),
        "phase": str(episode.get("phase", "NONE")),
        "expected_direction": expected_direction,
        "dealer_net_oi_percentile_156w": pct_now,
        "soft_upper": SOFT_UPPER,
        "soft_lower": SOFT_LOWER,
        "hard_upper_reference": HARD_UPPER_REFERENCE,
        "hard_lower_reference": HARD_LOWER_REFERENCE,
        "hard_extreme_reference": hard_extreme_reference,
        "raw_velocity_1w": raw_v1,
        "raw_velocity_2w_weekly": raw_v2,
        "release_velocity_1w": oriented_v1,
        "release_velocity_2w": oriented_v2,
        "flow_aligned_1w": flow_1w,
        "flow_aligned_2w": flow_2w,
        "flow_support": flow_support,
        "weeks_since_soft_release": episode.get("weeks_since_release", np.nan),
        "forward_evidence_weeks": FORWARD_EVIDENCE_WEEKS,
        "report_date": latest.get("report_date"),
        "error": None,
    }


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_fx_research_overlay(asset_class: str, contract_code: str) -> dict:
    """Load the research overlay only for the calibrated FX/TFF scope."""
    if str(asset_class) != "Currencies":
        return {
            "calibrated": False,
            "active": False,
            "scope": RESEARCH_SCOPE,
            "research_status": "NOT CALIBRATED",
            "expected_direction": 0,
            "error": None,
        }

    report_type = primary_report_for_asset_class(str(asset_class))
    if report_type != "tff":
        return {
            "calibrated": False,
            "active": False,
            "scope": RESEARCH_SCOPE,
            "research_status": "NOT CALIBRATED",
            "expected_direction": 0,
            "error": f"FX erwartet TFF, erhalten: {report_type}",
        }

    try:
        history = load_report_history(report_type, str(contract_code))
    except Exception as exc:
        return {
            "calibrated": True,
            "active": False,
            "scope": RESEARCH_SCOPE,
            "research_status": RESEARCH_STATUS,
            "expected_direction": 0,
            "error": str(exc),
        }

    return build_fx_dealer_research_context(history)


def classify_trader_overlay(
    research: Mapping[str, Any] | None,
    *,
    regime_stage: int,
    legacy_release: bool,
    price_confirming: bool = False,
) -> dict:
    """Translate the frozen research result into trader-facing context.

    This deliberately does NOT create a trade signal or change risk. 75/25 is
    only an early watch layer. Existing hard regime/release logic remains the
    gate for stronger actions.
    """
    r = dict(research or {})
    if not bool(r.get("calibrated", False)):
        return {
            "calibrated": False,
            "bias": "—",
            "confidence": "BESTEHENDE LOGIK",
            "timing": "—",
            "action": "BESTEHENDE REGIME-LOGIK",
            "tone": "neutral",
        }

    if not bool(r.get("active", False)):
        return {
            "calibrated": True,
            "bias": "NEUTRAL",
            "confidence": "WATCH",
            "timing": "WAITING",
            "action": "WARTEN",
            "tone": "neutral",
        }

    direction = int(np.sign(r.get("expected_direction", 0) or 0))
    bias = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"
    tone = "bull" if direction > 0 else "bear" if direction < 0 else "neutral"

    flow1 = bool(r.get("flow_aligned_1w", False))
    flow2 = bool(r.get("flow_aligned_2w", False))
    both_flow = flow1 and flow2
    any_flow = flow1 or flow2
    stage = max(0, min(5, int(regime_stage or 0)))

    if bool(legacy_release) and stage >= 4:
        confidence = "CONFIRMED"
    elif bool(legacy_release) or stage >= 2:
        confidence = "DEVELOPING"
    elif both_flow:
        confidence = "EARLY"
    elif any_flow:
        confidence = "WATCH"
    else:
        confidence = "WATCH"

    phase = str(r.get("phase", "NONE")).upper()
    weeks = _finite(r.get("weeks_since_soft_release"))
    if phase == "SOFT EXTREME":
        timing = "EARLY" if any_flow else "WAITING"
    elif phase == "SOFT RELEASE":
        if not np.isfinite(weeks) or weeks <= 2:
            timing = "ACTIVE"
        elif weeks <= 4:
            timing = "DEVELOPED"
        else:
            timing = "LATE"
    else:
        timing = "WAITING"

    # Conservative action layer:
    # Research-only 75/25 observations never bypass the existing hard regime gate.
    if stage <= 0:
        action = "BEOBACHTEN · EARLY FLOW" if both_flow else "WARTEN"
    elif stage == 1:
        action = "BEOBACHTEN · EARLY FLOW" if any_flow else "AUF TRANSITION WARTEN"
    elif timing == "LATE":
        action = "NICHT JAGEN · NUR PULLBACK"
    elif stage >= 4 and timing == "DEVELOPED":
        action = "PULLBACK / S&D PRÜFEN"
    elif stage >= 2 and timing in {"EARLY", "ACTIVE"}:
        action = "SETUP SUCHEN · S&D PRÜFEN"
    elif stage >= 4:
        action = "S&D / PULLBACK PRÜFEN"
    else:
        action = "BESTÄTIGUNG ABWARTEN"

    return {
        "calibrated": True,
        "bias": bias,
        "confidence": confidence,
        "timing": timing,
        "action": action,
        "tone": tone,
        "research_status": r.get("research_status", RESEARCH_STATUS),
        "flow_support": r.get("flow_support", "—"),
        "price_confirming": bool(price_confirming),
    }
