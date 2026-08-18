from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c_research_lab_has_automatic_robustness_scanner():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Auto Scanner" in text
    assert "scan_parameter_robustness" in text
    assert "scanner_findings" in text
    assert "Locked OOS" in text


def test_v311c_ui_states_oos_is_excluded_from_ranking():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "OOS wird nicht für Ranking oder Score verwendet" in text
    assert "Train + Validation" in text
    assert "Parameter-Nachbarschaft" in text


def test_v311c_does_not_add_direct_streamlit_plotly_renderer():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "st.plotly_chart(" not in text
