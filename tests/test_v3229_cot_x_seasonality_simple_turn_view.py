from pathlib import Path
import ast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def test_page_is_visually_reduced_to_three_steps():
    text = PAGE.read_text(encoding="utf-8")

    for token in (
        "1 · Seasonal Turn",
        "2 · Wer unterstützt den Turn?",
        "3 · Finaler Research Read",
        "Commercial-Seite",
        "Momentum-Funds",
        "Nonreportables",
    ):
        assert token in text

    for old_section in (
        "Confluence Map",
        "Macro / Micro Reference",
        "Phase Shift · Timing Modifier",
        "Multi-Group Positioning Path",
    ):
        assert old_section not in text


def test_asset_manager_is_details_only():
    text = PAGE.read_text(encoding="utf-8")

    assert "Asset Manager · langfristiger Kontext" in text
    assert "außerhalb des finalen Turn-Reads" in text


def test_three_group_selection_tff():
    from src.cot_x_seasonality import (
        simple_turn_group_selection,
    )

    flow_map = {
        "report_type": "tff",
        "groups": {},
    }

    out = simple_turn_group_selection(
        flow_map
    )

    assert out["commercial_key"] == "dealer"
    assert out["momentum_key"] == "leveraged_funds"


def test_three_group_selection_commodities():
    from src.cot_x_seasonality import (
        simple_turn_group_selection,
    )

    flow_map = {
        "report_type": "disaggregated",
        "groups": {},
    }

    out = simple_turn_group_selection(
        flow_map
    )

    assert out["commercial_key"] == "producer"
    assert out["momentum_key"] == "managed_money"


def test_4w_2w_1w_evolution_detects_reversal():
    from src.cot_x_seasonality import (
        group_4w_2w_1w_summary,
    )

    group = {
        "label": "Test",
        "role": "TEST",
        "net_oi_percentile": 50.0,
        "segments": [
            {
                "long_delta": 30.0,
                "short_delta": -20.0,
                "net_oi_delta": 0.05,
            },
            {
                "long_delta": -25.0,
                "short_delta": 4.0,
                "net_oi_delta": -0.029,
            },
            {
                "long_delta": 2.0,
                "short_delta": 4.0,
                "net_oi_delta": -0.002,
            },
        ],
    }

    out = group_4w_2w_1w_summary(
        group
    )

    assert out["available"] is True
    assert out["w4"]["direction"] == 1
    assert out["w2"]["direction"] == -1
    assert out["w1"]["direction"] == -1
    assert out["evolution"] == "BULLISH → BEARISH REVERSAL"


def test_top_read_uses_recent_momentum_and_commercial_flow():
    from src.cot_x_seasonality import (
        simple_cot_seasonality_turn_read,
    )

    seasonal = {
        "turn_direction": -1,
        "turn_type": "TOP",
        "turn_distance_days": 0,
        "h40": {
            "direction": -1,
            "quality": "ROBUST",
            "label": "ROBUST BEARISH",
        },
        "h60": {
            "direction": -1,
            "quality": "ROBUST",
            "label": "ROBUST BEARISH",
        },
    }

    def summary(d4, d2, d1, percentile=50.0):
        return {
            "available": True,
            "percentile": percentile,
            "evolution": "TEST",
            "w4": {"direction": d4},
            "w2": {"direction": d2},
            "w1": {"direction": d1},
        }

    groups = {
        "commercial": summary(1, -1, -1),
        "momentum": summary(1, -1, -1),
        "nonreportable": summary(1, 1, 1, percentile=90.0),
    }

    out = simple_cot_seasonality_turn_read(
        seasonal,
        groups,
    )

    assert out["quality"] == "STRONG"
    assert out["verdict"] == "BEARISH TOP EVIDENCE · STRONG"
    assert "Commercial-Seite" in out["supporters"]
    assert "Momentum-Funds" in out["supporters"]
    assert "Nonreportables" in out["supporters"]


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(encoding="utf-8")

    assert "V3.22.9" not in text
    assert "simple_cot_seasonality_turn_read" not in text


def test_files_parse():
    for path in (
        PAGE,
        ENGINE,
        WATCH,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
