from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "research_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_positioning_dynamics_subtabs_are_removed():
    text = _text()
    assert "dyn_state, dyn_depth, dyn_flow, dyn_scanner, dyn_scope = st.tabs(" not in text
    assert "dyn_state = st.container()" in text
    assert "dyn_flow = st.container()" in text
    assert "dyn_scanner = st.container()" in text


def test_vertical_research_stages_are_visible():
    text = _text()
    for marker in (
        "2 · Structural State",
        "3 · Flow Dynamics",
        "4 · Candidate Validation",
        "5 · Reviewed Hypotheses",
        "6 · Frozen OOS",
    ):
        assert marker in text


def test_research_scope_is_collapsed_methodology():
    text = _text()
    assert "Methodik · Scope, offene Fragen & Export" in text
    assert "with dyn_scope:" not in text


def test_detail_focus_is_not_confused_with_scanner_universe():
    text = _text()
    assert "Detail-Lookback" in text
    assert "Detail-Threshold" in text
    assert "Der Robustness Scanner untersucht weiterhin automatisch" in text


def test_review_and_freeze_are_bound_to_full_research_context():
    text = _text()
    assert 'f"v311c4_reviewed_ids|{research_context_key}"' in text
    assert 'f"{research_context_key}|{reviewed_signature}"' in text


def test_legacy_ui_markers_remain_only_for_regression_history():
    text = _text()
    assert "# Depth & Duration" in text
    assert "# Velocity & Acceleration" in text
    assert "# Auto Scanner" in text
    assert "# Legacy test marker: Reviewed Shortlist · manuelle Bestätigung" in text
    assert "# Legacy test marker: Pre-OOS Freeze Gate" in text


def test_no_direct_streamlit_plotly_chart_is_added():
    assert "st.plotly_chart(" not in _text()
