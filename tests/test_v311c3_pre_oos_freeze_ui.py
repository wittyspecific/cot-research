from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c3_has_freeze_gate():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Pre-OOS Freeze Gate" in text
    assert "Shortlist jetzt einfrieren" in text
    assert "OOS bleibt gesperrt. Die Shortlist ist noch NICHT eingefroren." in text


def test_v311c3_gates_oos_reveal():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "v311c3_frozen_snapshot" in text
    assert "OOS REVEAL GESPERRT" in text
    assert "Frozen OOS Reveal" in text


def test_v311c3_removes_legacy_positive_claim():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Monotonie-Hinweis: Stärkerer Flow zeigt in Train und Validation überwiegend höhere directional Returns." not in text
    assert "Legacy-Schrittquote" in text
