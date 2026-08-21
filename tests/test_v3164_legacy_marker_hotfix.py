from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "yield_spreads.py"


def test_visible_version_is_v3164():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.4 · RBA 403 TRANSPORT FIX" in text


def test_all_legacy_markers_are_preserved():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.1 · HISTORICALLY NORMALIZED 2Y YIELD SPREADS" in text
    assert "V3.16.2 · REPAIRED OFFICIAL 2Y DATA ADAPTERS" in text
    assert "V3.16.3 · OFFICIAL 2Y ADAPTERS COMPLETE" in text
