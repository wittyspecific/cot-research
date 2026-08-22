from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
COT_PAGE = ROOT / "pages" / "cot_price_analog.py"
FX_PAGE = ROOT / "pages" / "fx_relative_cot_analog.py"
ADVANCED_PAGE = ROOT / "pages" / "analog_diagnostics.py"


def _section_items(text: str, wanted: str):
    tree = ast.parse(
        text,
        filename=str(APP),
    )

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Dict,
        ):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and isinstance(
                    key.value,
                    str,
                )
                and wanted
                in key.value.upper()
                and isinstance(
                    value,
                    ast.List,
                )
            ):
                lines = text.splitlines()
                return [
                    "\n".join(
                        lines[
                            item.lineno - 1:
                            item.end_lineno
                        ]
                    )
                    for item in value.elts
                ]

    raise AssertionError(
        f"Navigation section containing {wanted!r} not found"
    )


def test_main_cot_price_page_is_compact():
    text = COT_PAGE.read_text(
        encoding="utf-8"
    )

    assert "1 · Current Setup Fingerprint" not in text
    assert "1 · Historical Analog Read" in text
    assert "2 · Price Path Comparison" in text
    assert "Historische Match-Details" in text


def test_main_fx_relative_page_is_compact():
    text = FX_PAGE.read_text(
        encoding="utf-8"
    )

    assert "1 · Relative FX Setup" not in text
    assert "1 · Historical FX Analog Read" in text
    assert "2 · FX Price Path Comparison" in text
    assert "Historische Match-Details" in text


def test_advanced_page_contains_both_fingerprints():
    text = ADVANCED_PAGE.read_text(
        encoding="utf-8"
    )

    for token in (
        "Analog Setup Diagnostics",
        "COT × Price · Current Setup Fingerprint",
        "FX Relative COT · Relative Setup Fingerprint",
        "4W Δ Long/OI",
        "Relative Net/OI",
        "CANADIAN DOLLAR",
        "Kein DXY-COT",
    ):
        assert token.lower() in text.lower()


def test_advanced_navigation_contains_diagnostics_page():
    text = APP.read_text(
        encoding="utf-8"
    )

    advanced = _section_items(
        text,
        "ADVANCED",
    )

    assert any(
        "pages/analog_diagnostics.py"
        in item
        for item in advanced
    )


def test_files_parse():
    for path in (
        APP,
        COT_PAGE,
        FX_PAGE,
        ADVANCED_PAGE,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
