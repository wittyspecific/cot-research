from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "research_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_v312d_cross_market_diagnostics_exist():
    text = _text()
    assert "4C · Cross-Market Diagnostics" in text
    assert "Flow Redundancy" in text
    assert "Leave-One-Market-Out" in text
    assert "Parameter Neighborhood" in text
    assert "Coverage · positiv / eligible / total" in text


def test_v312d_reuses_train_frozen_cutoffs_and_events():
    text = _text()
    assert "events_by_market" in text
    assert "flow_cutoff_train" in (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")
    assert "TRAIN+VALIDATION" in (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")


def test_v312d_is_pre_oos_only():
    module = (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")
    assert "OOS dates are excluded" in module
    assert "OOS remains irrelevant" in module


def test_v312d_no_direct_streamlit_plotly_renderer():
    assert "st.plotly_chart(" not in _text()
