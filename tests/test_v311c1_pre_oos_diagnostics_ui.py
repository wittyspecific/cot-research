from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c1_pre_oos_diagnostics_are_exposed():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Pre-OOS Diagnose" in text
    assert "Event Overlap · Top Flow" in text
    assert "Incremental Value · Flow vs. State" in text
    assert "Monotonicity · wird stärkerer Flow tatsächlich besser?" in text


def test_v311c1_diagnostics_do_not_use_oos():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Alle Pre-OOS-Diagnosen verwenden ausschließlich Train + Validation" in text
    assert "Locked OOS bleibt unangetastet" in text


def test_v311c1_adds_no_new_plotly_chart():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "st.plotly_chart(" not in text
