from pathlib import Path

import pandas as pd

from src.config import NET_LOWER_PERCENTILE, NET_UPPER_PERCENTILE
from src.research_informed_positioning import (
    HARD_LOWER_REFERENCE,
    HARD_UPPER_REFERENCE,
    SOFT_LOWER,
    SOFT_UPPER,
    classify_trader_overlay,
    directional_release_flow,
    soft_episode_context,
)


ROOT = Path(__file__).resolve().parents[1]


def test_research_soft_region_does_not_replace_hard_production_gate():
    assert (SOFT_UPPER, SOFT_LOWER) == (75.0, 25.0)
    assert (HARD_UPPER_REFERENCE, HARD_LOWER_REFERENCE) == (80.0, 20.0)
    assert (NET_UPPER_PERCENTILE, NET_LOWER_PERCENTILE) == (80, 20)


def test_directional_raw_release_flow_has_research_orientation():
    assert directional_release_flow(-100.0, 1) == 100.0
    assert directional_release_flow(100.0, -1) == 100.0
    assert directional_release_flow(100.0, 1) == -100.0


def test_soft_episode_tracks_recent_release_without_reoptimizing():
    pct = pd.Series([50, 76, 83, 79, 72, 60], dtype=float)
    out = soft_episode_context(pct, upper=75, lower=25, release_active_weeks=6)
    assert out["active"] is True
    assert out["phase"] == "SOFT RELEASE"
    assert out["zone"] == 1


def test_early_research_never_bypasses_hard_regime_gate():
    research = {
        "calibrated": True,
        "active": True,
        "phase": "SOFT EXTREME",
        "expected_direction": 1,
        "flow_aligned_1w": True,
        "flow_aligned_2w": True,
        "flow_support": "1–2W ALIGNED",
    }
    out = classify_trader_overlay(
        research,
        regime_stage=0,
        legacy_release=False,
        price_confirming=False,
    )
    assert out["bias"] == "BULLISH"
    assert out["confidence"] == "EARLY"
    assert out["action"] == "BEOBACHTEN · EARLY FLOW"
    assert "SETUP SUCHEN" not in out["action"]


def test_confirmed_regime_can_surface_setup_search_not_trade_execution():
    research = {
        "calibrated": True,
        "active": True,
        "phase": "SOFT RELEASE",
        "expected_direction": -1,
        "weeks_since_soft_release": 1,
        "flow_aligned_1w": True,
        "flow_aligned_2w": True,
        "flow_support": "1–2W ALIGNED",
    }
    out = classify_trader_overlay(
        research,
        regime_stage=4,
        legacy_release=True,
        price_confirming=False,
    )
    assert out["bias"] == "BEARISH"
    assert out["confidence"] == "CONFIRMED"
    assert out["timing"] == "ACTIVE"
    assert out["action"] == "SETUP SUCHEN · S&D PRÜFEN"


def test_ui_contains_bias_confidence_timing_action_and_early_fx_watch():
    market = (ROOT / "pages/marktanalyse.py").read_text(encoding="utf-8")
    watch = (ROOT / "pages/watchlist.py").read_text(encoding="utf-8")
    assert "RESEARCH-INFORMED FX OVERLAY" in market
    for label in ("BIAS", "CONFIDENCE", "TIMING", "ACTION"):
        assert label in market
    assert "Early FX Watch" in watch
    assert "75/25" in watch
