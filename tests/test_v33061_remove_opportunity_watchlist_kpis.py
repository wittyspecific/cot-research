from pathlib import Path
import ast
import hashlib

ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MANIFEST = ROOT / "docs" / "V3293_WATCHLIST_SHA256.txt"


def _source(path):
    return path.read_text(encoding="utf-8")


def test_v33061_cleanup_is_installed():
    source = _source(OPPORTUNITY)

    assert "V3.30.6.1 · OPPORTUNITY WATCHLIST KPI CLEANUP" in source
    assert "def _apply_v33061_hide_embedded_watchlist_summary(" in source


def test_v33061_hides_summary_containers():
    source = _source(OPPORTUNITY)

    for token in (
        ".sw-cards,",
        ".sw-legend,",
        ".sl-kpis,",
        ".sl-logic {",
        "display: none !important",
    ):
        assert token in source


def test_v33061_cleanup_runs_after_watchlist_render():
    source = _source(OPPORTUNITY)

    run_pos = source.index("_run_legacy_watchlist_with_routing()")
    hide_pos = source.index(
        "_apply_v33061_hide_embedded_watchlist_summary()",
        run_pos,
    )

    assert run_pos < hide_pos


def test_v33061_original_watchlist_stays_byte_identical():
    if not MANIFEST.exists():
        return

    expected = MANIFEST.read_text(
        encoding="utf-8"
    ).strip().split()[0]

    actual = hashlib.sha256(
        WATCHLIST.read_bytes()
    ).hexdigest()

    assert actual == expected


def test_v33061_opportunity_page_parses():
    ast.parse(
        _source(OPPORTUNITY),
        filename=str(OPPORTUNITY),
    )
