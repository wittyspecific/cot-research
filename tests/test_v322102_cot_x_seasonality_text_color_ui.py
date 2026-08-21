from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_direction_is_carried_by_text_color_not_colored_status_boxes():
    text = _text()

    start = text.index("def _status_card(")
    end = text.index("\ndef _banner(", start)
    card = text[start:end]

    assert "background:#ffffff;" in card
    assert "color:{palette['text']};" in card
    assert "background:{palette['bg']}" not in card


def test_banner_is_text_only():
    text = _text()

    start = text.index("def _banner(")
    end = text.index("\ndef _flow_label(", start)
    banner = text[start:end]

    assert "color:{palette['text']};" in banner
    assert "border-left" not in banner
    assert "background:{palette['bg']}" not in banner


def test_flow_labels_have_no_pill_background():
    text = _text()

    start = text.index("def _flow_chip(")
    end = text.index("\ndef _turn_state(", start)
    segment = text[start:end]

    assert "_direction_text_color(" in segment
    assert "font-weight:800" in segment
    assert "border-radius:999px" not in segment
    assert 'background:{palette["soft"]}' not in segment


def test_group_turn_relation_is_colored_text_only():
    text = _text()

    start = text.index("def _group_card(")
    end = text.index("\ndef _localized_final_read(", start)
    segment = text[start:end]

    assert "color:{relation_color};" in segment
    assert "background:{relation_palette" not in segment


def test_top_bottom_semantics_survive():
    text = _text()

    assert "SEASONAL TOP · ROBUST BEARISH" in text
    assert "SEASONAL BOTTOM · ROBUST BULLISH" in text
    assert '"#ef4444"' in text
    assert '"#22c55e"' in text


def test_watchlist_engine_untouched():
    assert "V3.22.10.2" not in WATCH.read_text(encoding="utf-8")
    assert "V3.22.10.2" not in ENGINE.read_text(encoding="utf-8")


def test_files_parse():
    for path in (PAGE, ENGINE, WATCH):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
