from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_is_grouped_into_three_sections():
    text = (ROOT / "app.py").read_text()
    assert '"SCHNELLÜBERBLICK": [' in text
    assert '"MARKT & PORTFOLIO": [' in text
    assert '"RESEARCH": [' in text
    assert 'st.navigation(pages, position="sidebar")' in text


def test_quick_overview_contains_only_watchlist_and_cockpit_first():
    text = (ROOT / "app.py").read_text()
    quick = text.split('"SCHNELLÜBERBLICK": [', 1)[1].split('"MARKT & PORTFOLIO": [', 1)[0]
    assert 'pages/watchlist.py' in quick
    assert 'pages/risk_cockpit.py' in quick
    assert 'pages/portfolio_risk.py' not in quick
    assert 'pages/forex_matrix.py' not in quick
    assert 'pages/research_lab.py' not in quick


def test_watchlist_remains_default_page():
    text = (ROOT / "app.py").read_text()
    watchlist = text.split('"pages/watchlist.py"', 1)[1].split('),', 1)[0]
    assert 'default=True' in watchlist


def test_detail_and_research_order_is_intentional():
    text = (ROOT / "app.py").read_text()
    assert text.index('pages/marktanalyse.py') < text.index('pages/forex_matrix.py')
    assert text.index('pages/forex_matrix.py') < text.index('pages/portfolio_risk.py')
    assert text.index('pages/research_lab.py') < text.index('pages/datenmodell.py')
