from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
SCAN = ROOT / "src" / "watchlist.py"


def test_v3144_scan_exposes_macro_and_micro_age():
    text = SCAN.read_text(encoding="utf-8")
    assert "macro_status_age_weeks" in text
    assert "micro_status_age_weeks" in text
    assert '"macro_status_age_weeks"' in text
    assert '"micro_status_age_weeks"' in text


def test_v3144_watchlist_displays_age_under_existing_chips():
    text = WATCH.read_text(encoding="utf-8")
    assert "sl-age" in text
    assert 'row.get("macro_status_age_weeks"' in text
    assert 'row.get("micro_status_age_weeks"' in text
    assert "Release seit" in text
    assert 'f"seit {macro_age_weeks}W"' in text
    assert 'f"seit {micro_age_weeks}W"' in text


def test_v3144_age_does_not_enter_decision_core():
    text = (
        ROOT / "src" / "watchlist_macro_micro.py"
    ).read_text(encoding="utf-8")
    assert "status_age" not in text


def test_v3144_watchlist_still_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"))
