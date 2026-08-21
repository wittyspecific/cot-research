from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_top_bottom_have_directional_ui_colors():
    text = _text()

    assert 'turn_tone = (' in text
    assert '"bearish"' in text
    assert '"bullish"' in text
    assert "SEASONAL TOP · ROBUST BEARISH" in text
    assert "SEASONAL BOTTOM · ROBUST BULLISH" in text
    assert '"#ef4444"' in text
    assert '"#22c55e"' in text


def test_main_view_is_three_visual_steps():
    text = _text()

    for token in (
        "1 · Seasonal Turn",
        "2 · Wer unterstützt den Turn?",
        "3 · Finaler Research Read",
        "Commercial-Seite",
        "Momentum-Funds",
        "Nonreportables (konträr)",
    ):
        assert token in text


def test_momentum_is_explicitly_highlighted():
    text = _text()

    assert "Momentum-Funds sind für das kurzfristige Turn-Timing besonders wichtig" in text
    assert "momentum=True" in text


def test_asset_manager_stays_details_only():
    text = _text()

    assert "Asset Manager · langfristiger Kontext" in text
    assert "außerhalb des finalen Turn-Reads" in text


def test_old_verbose_sections_stay_removed():
    text = _text()

    for removed in (
        "Confluence Map",
        "Macro / Micro Reference",
        "Phase Shift · Timing Modifier",
        "Multi-Group Positioning Path",
        "Chronologischer Flow Path",
    ):
        assert removed not in text


def test_watchlist_and_engine_are_not_coupled_to_ui_patch():
    watch = WATCH.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")

    assert "V3.22.10" not in watch
    assert "V3.22.10" not in engine
    assert "TURN UI" not in watch


def test_files_parse():
    for path in (
        PAGE,
        ENGINE,
        WATCH,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
