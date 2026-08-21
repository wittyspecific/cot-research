from pathlib import Path
import ast

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def test_multigroup_page_sections_exist():
    text = PAGE.read_text(encoding="utf-8")

    for token in (
        "2 · Wer unterstützt den Turn?",
        "Commercial-Seite",
        "Momentum-Funds",
        "Nonreportables",
        "Details · Long / Short / Net Deltas",
        "Asset Manager · langfristiger Kontext",
        "nicht als echtes Retail interpretiert",
    ):
        assert token in text

    for removed in (
        "Multi-Group Positioning Path",
        "Chronologischer Flow Path",
        "Seasonal Turn × Positioning Evidence",
    ):
        assert removed not in text



def test_tff_roles_are_explicit():
    from src.cot_x_seasonality import GROUP_ROLES

    specs = {
        row["key"]: row
        for row in GROUP_ROLES["tff"]
    }

    assert specs["asset_manager"]["role"] == "INSTITUTIONAL FLOW"
    assert specs["leveraged_funds"]["role"] == "SPECULATIVE FLOW"
    assert specs["dealer"]["directional"] is False
    assert specs["nonreportable"]["directional"] is False


def test_chronological_segments_are_non_overlapping():
    from src.cot_x_seasonality import build_group_flow_map

    dates = pd.date_range(
        "2026-01-06",
        periods=5,
        freq="7D",
    )

    # W-4 -> W-2: strongly bullish
    # W-2 -> W-1: strongly bearish
    # W-1 -> NOW: both sides build, shorts slightly more
    df = pd.DataFrame(
        {
            "report_date": dates,
            "open_interest_all": [1000.0] * 5,
            "dealer_long": [100, 100, 100, 100, 100],
            "dealer_short": [100, 100, 100, 100, 100],
            "asset_manager_long": [100, 110, 132, 107, 110],
            "asset_manager_short": [100, 95, 80, 84, 88],
            "leveraged_funds_long": [100, 110, 130, 105, 108],
            "leveraged_funds_short": [100, 94, 80, 84, 89],
            "other_reportable_long": [100] * 5,
            "other_reportable_short": [100] * 5,
            "nonreportable_long": [100, 100, 100, 100, 100],
            "nonreportable_short": [100, 100, 100, 100, 100],
            "asset_manager_net_oi_percentile": [50, 55, 60, 55, 52],
            "leveraged_funds_net_oi_percentile": [50, 60, 70, 55, 50],
            "dealer_net_oi_percentile": [50] * 5,
            "nonreportable_net_oi_percentile": [50] * 5,
        }
    )

    out = build_group_flow_map(
        df,
        "tff",
    )

    am = out["groups"]["asset_manager"]
    segments = am["segments"]

    assert [row["segment"] for row in segments] == [
        "W-4 → W-2",
        "W-2 → W-1",
        "W-1 → NOW",
    ]

    assert segments[0]["direction"] == 1
    assert segments[1]["direction"] == -1
    assert segments[2]["direction"] == -1

    assert np.isclose(
        segments[0]["net_delta"],
        segments[0]["long_delta"] - segments[0]["short_delta"],
    )
    assert np.isclose(
        segments[1]["net_delta"],
        segments[1]["long_delta"] - segments[1]["short_delta"],
    )
    assert np.isclose(
        segments[2]["net_delta"],
        segments[2]["long_delta"] - segments[2]["short_delta"],
    )


def test_top_evidence_uses_asset_manager_and_leveraged_funds_roles():
    from src.cot_x_seasonality import (
        build_group_flow_map,
        positioning_turn_evidence,
    )

    dates = pd.date_range(
        "2026-01-06",
        periods=5,
        freq="7D",
    )

    df = pd.DataFrame(
        {
            "report_date": dates,
            "open_interest_all": [1000.0] * 5,
            "dealer_long": [100] * 5,
            "dealer_short": [100] * 5,
            "asset_manager_long": [100, 115, 140, 110, 105],
            "asset_manager_short": [100, 95, 80, 90, 100],
            "leveraged_funds_long": [100, 120, 145, 115, 105],
            "leveraged_funds_short": [100, 95, 75, 85, 100],
            "other_reportable_long": [100] * 5,
            "other_reportable_short": [100] * 5,
            "nonreportable_long": [100, 105, 110, 120, 130],
            "nonreportable_short": [100, 100, 100, 100, 100],
            "asset_manager_net_oi_percentile": [50, 60, 70, 55, 40],
            "leveraged_funds_net_oi_percentile": [50, 60, 75, 55, 35],
            "dealer_net_oi_percentile": [50] * 5,
            "nonreportable_net_oi_percentile": [50, 60, 70, 82, 90],
        }
    )

    flow_map = build_group_flow_map(
        df,
        "tff",
    )
    evidence = positioning_turn_evidence(
        flow_map,
        -1,
    )

    assert evidence["turn_name"] == "TOPPING"
    assert evidence["quality"] == "STRONG"
    assert "Asset Manager" in evidence["supporting_roles"]
    assert "Leveraged Funds" in evidence["supporting_roles"]
    assert "Nonreportable Extreme" in evidence["supporting_roles"]


def test_nonreportable_is_not_named_retail_in_engine():
    text = ENGINE.read_text(encoding="utf-8")

    assert "RESIDUAL / CONTRARIAN CONTEXT" in text
    assert "Retail" not in text
    assert "retail" not in text


def test_no_composite_score_or_watchlist_coupling():
    engine = ENGINE.read_text(encoding="utf-8")
    watch = WATCH.read_text(encoding="utf-8")

    for forbidden in (
        "composite_score",
        "ranking_score",
        "setup_score",
        "alignment_score",
        "total_score",
    ):
        assert forbidden not in engine

    assert "build_group_flow_map" not in watch
    assert "positioning_turn_evidence" not in watch
    assert "V3.22.8" not in watch


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
