from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def test_app_parses():
    ast.parse(
        APP.read_text(encoding="utf-8"),
        filename=str(APP),
    )


def test_yield_spreads_filter_accepts_german_title():
    text = APP.read_text(encoding="utf-8")

    assert (
        'not in {"Yield Spreads", "Zinskurven"}'
        in text
        or
        "not in {'Yield Spreads', 'Zinskurven'}"
        in text
    )


def test_old_english_only_filter_is_gone():
    text = APP.read_text(encoding="utf-8")

    assert (
        'if getattr(page, "title", None) != "Yield Spreads"'
        not in text
    )
