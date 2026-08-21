from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "yield_spreads.py"


def test_visible_version_remains_v3163():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.3 · OFFICIAL 2Y ADAPTERS COMPLETE" in text


def test_v3161_marker_is_preserved():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.1 · HISTORICALLY NORMALIZED 2Y YIELD SPREADS" in text


def test_v3162_marker_is_preserved():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.2 · REPAIRED OFFICIAL 2Y DATA ADAPTERS" in text


def test_current_yield_ui_contract_remains():
    text = PAGE.read_text(encoding="utf-8")
    assert "letzten fünf Kalenderjahre" in text
    assert "Rates Alignment" in text
    assert "EXTREME" in text
