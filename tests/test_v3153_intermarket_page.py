from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "intermarket.py"


def test_intermarket_page_exists():
    assert PAGE.exists()


def test_intermarket_page_parses():
    ast.parse(PAGE.read_text(encoding="utf-8"))


def test_intermarket_is_in_research_navigation():
    text = APP.read_text(encoding="utf-8")

    # V3.29.x:
    # Intermarket is no longer a standalone Research page. Its trader-facing
    # context is integrated into Marktanalyse; the legacy page remains
    # reachable through an Advanced wrapper.
    assert '"pages/market_analysis_hub.py"' in text
    assert '"pages/advanced_legacy_intermarket.py"' in text


def test_intermarket_is_directly_below_watchlist():
    text = APP.read_text(encoding="utf-8")

    # V3.29.x replaces the old Watchlist -> Intermarket sidebar ordering
    # with the new trader workflow.
    opportunity = text.index('"pages/opportunity_scanner.py"')
    market = text.index('"pages/market_analysis_hub.py"')
    currency = text.index('"pages/currency_strength_hub.py"')
    macro = text.index('"pages/macro_regime.py"')

    assert opportunity < market < currency < macro
