from pathlib import Path
import ast
import hashlib


ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MANIFEST = ROOT / "docs" / "V3293_WATCHLIST_SHA256.txt"


def test_opportunity_scanner_executes_original_watchlist():
    source = OPPORTUNITY.read_text(
        encoding="utf-8"
    )

    assert "LEGACY_WATCHLIST" in source
    assert "runpy.run_path(" in source
    assert 'run_name="__main__"' in source
    assert '"Beobachtungsliste"' in source


def test_generic_cot_scanner_backend_is_not_used_here():
    source = OPPORTUNITY.read_text(
        encoding="utf-8"
    )

    assert "cot_scan_asset_class" not in source
    assert '"COT Scanner"' not in source
    assert "position_strength" not in source


def test_seasonality_scanner_remains_separate():
    source = OPPORTUNITY.read_text(
        encoding="utf-8"
    )

    assert "seasonality_scan_asset_class" in source
    assert '"Seasonality Scanner"' in source


def test_original_watchlist_was_not_modified_by_installer():
    expected = MANIFEST.read_text(
        encoding="utf-8"
    ).strip()

    actual = hashlib.sha256(
        WATCHLIST.read_bytes()
    ).hexdigest()

    assert actual == expected


def test_opportunity_page_parses():
    ast.parse(
        OPPORTUNITY.read_text(
            encoding="utf-8"
        ),
        filename=str(OPPORTUNITY),
    )
