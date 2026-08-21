from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "cot_x_seasonality.py"
ENGINE = ROOT / "src" / "cot_x_seasonality.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_safe_html_renderer_exists():
    text = _text()

    assert "def _render_inline_html(" in text
    assert '"".join(' in text
    assert "line.strip()" in text
    assert "unsafe_allow_html=True" in text


def test_all_custom_cards_use_safe_renderer():
    text = _text()

    for fn_name in (
        "_status_card",
        "_banner",
        "_group_card",
    ):
        start = text.index(
            f"def {fn_name}("
        )

        next_def = text.find(
            "\ndef ",
            start + 5,
        )
        segment = (
            text[start:]
            if next_def < 0
            else text[start:next_def]
        )

        assert "_render_inline_html(" in segment


def test_group_card_still_contains_three_windows():
    text = _text()

    start = text.index(
        "def _group_card("
    )
    end = text.index(
        "\ndef _localized_final_read(",
        start,
    )
    segment = text[start:end]

    assert ">4W</div>" in segment
    assert ">2W</div>" in segment
    assert ">1W</div>" in segment
    assert "_flow_chip(summary.get('w4'))" in segment
    assert "_flow_chip(summary.get('w2'))" in segment
    assert "_flow_chip(summary.get('w1'))" in segment


def test_directional_turn_ui_survives():
    text = _text()

    assert "SEASONAL TOP · ROBUST BEARISH" in text
    assert "SEASONAL BOTTOM · ROBUST BULLISH" in text
    assert "Momentum-Funds" in text
    assert "Nonreportables (konträr)" in text


def test_watchlist_and_engine_untouched_by_fix():
    watch = WATCH.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")

    assert "V3.22.10.1" not in watch
    assert "_render_inline_html" not in engine


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
