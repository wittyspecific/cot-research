from pathlib import Path
import ast

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def test_page_is_registered_after_seasonality_edge_lab():
    text = APP.read_text(encoding="utf-8")
    assert text.index("pages/seasonality_edge_lab.py") < text.index("pages/cot_x_seasonality.py")
    assert "COT × Seasonality" in text


def test_page_contains_model_layers():
    text = PAGE.read_text(encoding="utf-8")

    for token in (
        "1 · Seasonal Turn",
        "2 · Wer unterstützt den Turn?",
        "3 · Finaler Research Read",
        "Commercial-Seite",
        "Momentum-Funds",
        "Nonreportables",
        "Research only",
    ):
        assert token in text

    for removed in (
        "Confluence Map",
        "Macro / Micro Reference",
        "Phase Shift · Timing Modifier",
    ):
        assert removed not in text



def test_engine_uses_no_composite_score():
    text = ENGINE.read_text(encoding="utf-8")
    for forbidden in ("composite_score", "ranking_score", "setup_score", "alignment_score", "total_score"):
        assert forbidden not in text


def test_flow_accounting_identity():
    from src.cot_x_seasonality import positioning_flow_from_history
    dates = pd.date_range("2026-01-06", periods=6, freq="7D")
    df = pd.DataFrame({
        "report_date": dates,
        "producer_long": [100, 110, 120, 130, 145, 160],
        "producer_short": [80, 82, 85, 90, 96, 100],
        "open_interest_all": [1000, 1005, 1010, 1015, 1020, 1025],
    })
    out = positioning_flow_from_history(df, "disaggregated")
    assert out["available"] is True
    assert out["identity_ok"] is True
    for weeks in (1, 2, 4):
        assert np.isclose(out[f"net_delta_{weeks}w"], out[f"long_delta_{weeks}w"] - out[f"short_delta_{weeks}w"])


def test_robust_horizon_requires_broad_agreement():
    from src.cot_x_seasonality import robust_horizon_summary
    df = pd.DataFrame({
        "history_years": [10, 15, 20, 30],
        "horizon_days": [40, 40, 40, 40],
        "direction": ["BULLISH", "BULLISH", "BULLISH", "MIXED"],
        "median_edge": [0.02, 0.01, 0.015, 0.0],
        "hit_rate_edge_pp": [10.0, 8.0, 9.0, 0.0],
    })
    out = robust_horizon_summary(df, 40)
    assert out["direction"] == 1
    assert out["quality"] == "ROBUST"
    assert out["bullish_windows"] == 3


def test_pre_release_alignment_is_watch_not_entry():
    from src.cot_x_seasonality import classify_cot_x_seasonality
    result = classify_cot_x_seasonality(
        {"direction": 1, "phase": "TRANSITION", "active": False},
        {"edge_direction": 1, "turn_direction": 1},
        {"directional_interpretation": True, "flow_direction_4w": 1, "recent_flow": "CONFIRMING"},
        {"usable": False},
    )
    assert result["status"] == "EARLY BULLISH TRANSITION WATCH"
    assert "ENTRY" not in result["status"]


def test_watchlist_does_not_import_new_model():
    text = WATCH.read_text(encoding="utf-8")
    assert "cot_x_seasonality" not in text
    assert "V3.22.7" not in text


def test_files_parse():
    for path in (APP, PAGE, ENGINE, WATCH):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
