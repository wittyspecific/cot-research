from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis import hedger_cycle_state, net_validation

ROOT = Path(__file__).resolve().parents[1]


def _cot(percentiles, indexes=None):
    indexes = indexes if indexes is not None else [50.0] * len(percentiles)
    return pd.DataFrame({
        "report_date": pd.date_range("2026-01-01", periods=len(percentiles), freq="7D"),
        "commercial_net_percentile": [float(x) for x in percentiles],
        "commercial_index": [float(x) for x in indexes],
        "commercial_net": np.arange(len(percentiles), dtype=float) + 1000.0,
    })


def test_legacy_26w_index_extreme_does_not_create_primary_state():
    out = hedger_cycle_state(_cot([45, 50, 55, 60], indexes=[100, 100, 100, 100]))
    assert out["phase"] == "NONE"
    assert out["direction"] == 0
    assert out["source_metric"] == "commercial_net_percentile_156w"


def test_upper_156w_extreme_is_state_without_direction_even_if_index_neutral():
    out = hedger_cycle_state(_cot([60, 82, 94, 98], indexes=[50, 50, 50, 50]))
    assert out["phase"] == "EXTREME"
    assert out["direction"] == 0
    assert out["extreme_direction"] == 1
    assert out["current_percentile"] == 98
    assert out["extreme_percentile"] == 98
    assert "FULL HEDGE" in out["state"]


def test_transition_is_measured_before_upper_release_but_not_directional():
    out = hedger_cycle_state(_cot([60, 82, 98, 96, 91]))
    assert out["phase"] == "EXTREME"
    assert out["transition"] == "EARLY RELEASE · STILL EXTREME"
    assert out["direction"] == 0
    assert out["percentile_change_1w"] == -5
    assert out["distance_from_extreme"] == -7


def test_leaving_upper_156w_extreme_confirms_bullish_release():
    out = hedger_cycle_state(_cot([60, 82, 98, 94, 79]))
    assert out["phase"] == "RELEASE"
    assert out["transition"] == "CONFIRMED RELEASE"
    assert out["direction"] == 1
    assert out["extreme_percentile"] == 98
    assert out["current_percentile"] == 79
    assert out["percentile_change_1w"] == -15


def test_leaving_lower_156w_extreme_confirms_bearish_release():
    out = hedger_cycle_state(_cot([40, 18, 7, 12, 21]))
    assert out["phase"] == "RELEASE"
    assert out["direction"] == -1
    assert out["extreme_percentile"] == 7
    assert out["current_percentile"] == 21


def test_release_confirmation_uses_episode_extreme_not_current_commercial_pct():
    cycle = hedger_cycle_state(_cot([60, 82, 98, 94, 79]))
    row = pd.Series({
        "commercial_net_percentile": 79.0,
        "retail_net_percentile": 12.0,
    })
    result = net_validation(row, "BULLISH", upper=80, lower=20, cycle=cycle)
    assert result["commercial_confirmed"] is True
    assert result["retail_confirmed"] is True
    assert result["status"] == "CONFIRMED"


def test_ui_keeps_156w_primary_and_26w_advanced():
    market = (ROOT / "pages/marktanalyse.py").read_text(encoding="utf-8")
    watch = (ROOT / "pages/watchlist.py").read_text(encoding="utf-8")
    fx = (ROOT / "pages/forex_matrix.py").read_text(encoding="utf-8")
    assert "Commercial Positioning · 156W" in market
    assert "Advanced · 26W COT-Index anzeigen" in market
    assert "Commercial Net Percentile 156W ist die Ausgangslage" in watch
    assert "156W RELEASE CONTEXT" in fx


def test_snapshot_stores_state_transition_release_and_keeps_legacy_index():
    snapshot = (ROOT / "src/trade_snapshot.py").read_text(encoding="utf-8")
    assert 'SNAPSHOT_BUILDER_VERSION = "V3.10.0"' in snapshot
    assert '"commercial_net_percentile_156w"' in snapshot
    assert '"commercial_percentile_delta_1w"' in snapshot
    assert '"commercial_percentile_delta_4w"' in snapshot
    assert '"commercial_percentile_distance_from_extreme"' in snapshot
    assert '"commercial_index"' in snapshot
