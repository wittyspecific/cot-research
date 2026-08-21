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
    assert '"pages/intermarket.py"' in text
    assert 'title="Intermarket"' in text


def test_intermarket_is_directly_below_watchlist():
    text = APP.read_text(encoding="utf-8")
    watch = text.index('"pages/watchlist.py"')
    intermarket = text.index('"pages/intermarket.py"')
    marketanalysis = text.index('"pages/marktanalyse.py"')
    assert watch < intermarket < marketanalysis
