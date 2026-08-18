from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c2_strict_monotonicity_is_visible():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Strict Monotonicity · C.2" in text
    assert "ORDERED TRAIN" in text
    assert "SPEARMAN VALIDATION" in text
    assert "Q4 − Q1 VALIDATION" in text
    assert "STRICT VERDICT" in text


def test_v311c2_has_distinct_pre_oos_shortlist():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Pre-OOS Shortlist · unterschiedliche Hypothesen" in text
    assert "REDUNDANT ≥ 80%" in text
    assert "distinct_candidate_shortlist" in text


def test_v311c2_keeps_oos_out_of_strict_diagnostics():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "kein OOS verwendet" in text
    assert "vor dem OOS-Reveal eingefroren" in text


def test_v311c2_adds_no_direct_plotly_renderer():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "st.plotly_chart(" not in text
