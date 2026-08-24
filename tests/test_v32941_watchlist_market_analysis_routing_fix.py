from pathlib import Path
import ast
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MANIFEST = ROOT / "docs" / "V3293_WATCHLIST_SHA256.txt"


def test_routing_bridge_is_present():
    source = OPPORTUNITY.read_text(encoding="utf-8")
    assert "V3.29.4.1 · LEGACY WATCHLIST ROUTING BRIDGE" in source
    assert '"pages/marktanalyse.py"' in source
    assert '"pages/market_analysis_hub.py"' in source


def test_market_context_is_translated_for_new_hub():
    source = OPPORTUNITY.read_text(encoding="utf-8")
    assert '"selected_market"' in source
    assert '"_market_context_handoff"' in source
    assert '"research_market_handoff"' in source
    assert '"kind": "classic"' in source


def test_watchlist_runs_through_bridge():
    source = OPPORTUNITY.read_text(encoding="utf-8")
    assert "_run_legacy_watchlist_with_routing()" in source


def test_original_watchlist_remains_byte_identical():
    expected = MANIFEST.read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(WATCHLIST.read_bytes()).hexdigest()
    assert actual == expected


def test_modified_page_parses():
    ast.parse(
        OPPORTUNITY.read_text(encoding="utf-8"),
        filename=str(OPPORTUNITY),
    )
