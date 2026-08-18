from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c4_has_reviewed_shortlist_ui():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Reviewed Shortlist · manuelle Bestätigung" in text
    assert "Research-Hypothesen für OOS auswählen" in text
    assert "reviewed_shortlist(" in text
    assert "candidate_freeze_id" in text


def test_v311c4_freezes_reviewed_not_auto_shortlist():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "reviewed_freeze_shortlist" in text
    assert "build_pre_oos_freeze_snapshot(" in text
    assert "reviewed_freeze_shortlist," in text
    assert "disabled=reviewed_freeze_shortlist.empty" in text


def test_v311c4_warns_selection_change_invalidates_prior_freeze():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Auswahl geändert" in text
    assert "erneut eingefroren" in text
