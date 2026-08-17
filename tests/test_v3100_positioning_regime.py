from pathlib import Path

import numpy as np
import pandas as pd

from src.positioning_regime import (
    classify_group_transition,
    classify_nonreportable_context,
    classify_price_structure,
    classify_regime_stage,
    enrich_report_group_percentiles,
)

ROOT = Path(__file__).resolve().parents[1]


def test_report_groups_get_156w_and_1_2_4w_transitions():
    n = 170
    df = pd.DataFrame({
        "report_date": pd.date_range("2023-01-03", periods=n, freq="7D"),
        "open_interest_all": np.full(n, 100000.0),
        "asset_manager_long": np.arange(n, dtype=float) + 1000,
        "asset_manager_short": np.full(n, 900.0),
        "leveraged_funds_long": np.full(n, 500.0),
        "leveraged_funds_short": np.arange(n, dtype=float) + 400,
        "nonreportable_long": np.arange(n, dtype=float) + 200,
        "nonreportable_short": np.full(n, 150.0),
    })
    out = enrich_report_group_percentiles(df)
    for suffix in ("net_percentile_156w", "pct_delta_1w", "pct_delta_2w", "pct_delta_4w"):
        assert f"asset_manager_{suffix}" in out.columns
        assert f"leveraged_funds_{suffix}" in out.columns


def test_group_transition_is_direction_aware_over_1_to_4_weeks():
    bull = classify_group_transition(
        percentile=42,
        delta_1w=3,
        delta_2w=6,
        delta_4w=12,
        expected_direction=1,
    )
    assert bull["aligned"] is True
    assert bull["label"] in {"TRENDABBAU", "DREHT"}

    bear = classify_group_transition(
        percentile=58,
        delta_1w=-3,
        delta_2w=-6,
        delta_4w=-12,
        expected_direction=-1,
    )
    assert bear["aligned"] is True


def test_nonreportable_is_contrarian_context_not_retail_alias():
    bull = classify_nonreportable_context(12, 1)
    assert bull["contrarian"] is True
    assert bull["strong"] is True
    bear = classify_nonreportable_context(91, -1)
    assert bear["contrarian"] is True
    assert bear["strong"] is True


def test_pipeline_does_not_skip_commercial_release_gate():
    stage = classify_regime_stage(
        cycle_phase="EXTREME",
        commercial_transition="EARLY RELEASE · STILL EXTREME",
        institutional={"aligned": True},
        trend={"aligned": True},
        nonreportable={"contrarian": True},
        price={"confirming": True},
    )
    assert stage["stage"] == 3
    assert stage["label"] == "CROSS-GROUP SHIFT"

    released = classify_regime_stage(
        cycle_phase="RELEASE",
        commercial_transition="CONFIRMED RELEASE",
        institutional={"aligned": True},
        trend={"aligned": True},
        nonreportable={"contrarian": True},
        price={"confirming": True},
    )
    assert released["stage"] == 5
    assert released["label"] == "CONTEXT READY"


def test_price_context_is_late_confirmation_only():
    idx = pd.date_range("2026-01-01", periods=90, freq="D")
    close = pd.Series(np.linspace(100, 90, 70).tolist() + np.linspace(90, 110, 20).tolist(), index=idx)
    result = classify_price_structure(pd.DataFrame({"close": close}), 1)
    assert result["label"] in {"STRUCTURE BREAK ↑", "TURNING ↑"}
    assert result["confirming"] is True


def test_watchlist_uses_divide_and_conquer_ui_and_hides_26w_from_main_table():
    source = (ROOT / "pages/watchlist.py").read_text(encoding="utf-8")
    assert "Commercial Net Percentile 156W ist die Ausgangslage" in source
    assert "Asset Manager + Leveraged Funds" in source
    assert "Producer/Merchant + Managed Money" in source
    assert "Nonreportable" in source
    assert "CONTEXT READY ist noch kein Trade" in source
    assert "Der 26W-COT-Index ist aus dieser Hauptansicht entfernt" in source
    assert "4/4 Voll" not in source
