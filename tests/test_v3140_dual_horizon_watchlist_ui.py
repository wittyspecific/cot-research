from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def test_dual_horizon_is_merged_into_main_watchlist():
    text = _text()
    assert "def _merge_dual_horizon_into_pipeline(" in text
    assert "pipeline = _merge_dual_horizon_into_pipeline(" in text
    assert "dual_horizon_active" in text


def test_watchlist_explicitly_shows_156w_and_26w_side_by_side():
    text = _text()
    assert "<th>156W Regime</th>" in text
    assert "<th>26W Timing</th>" in text
    assert "Commercial 156W" in text
    assert "COT26 C" in text


def test_transition_watch_filter_exists():
    text = _text()
    assert '"Transition Watch"' in text
    assert 'str.contains(' in text
    assert '"TRANSITION WATCH|REGIME PRESSURE"' in text


def test_existing_cross_group_confidence_remains_visible():
    text = _text()
    assert "<th>Confidence</th>" in text
    assert "regime_status" in text


def test_old_bias_timing_markers_remain_for_v313b_regression_history():
    text = _text()
    assert "# Legacy V3.13B header marker: <th>Bias</th>" in text
    assert "# Legacy V3.13B header marker: <th>Timing</th>" in text
