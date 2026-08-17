from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_uses_v390_workspace_hierarchy():
    text = (ROOT / "app.py").read_text()
    assert '"WORKSPACE": [' in text
    assert '"RESEARCH": [' in text
    assert '"TRADING": [' in text
    assert '"ADVANCED": [' in text
    assert 'st.navigation(pages, position="sidebar")' in text


def test_dashboard_is_default_and_watchlist_is_research():
    text = (ROOT / "app.py").read_text()
    dashboard = text.split('"pages/dashboard.py"', 1)[1].split('),', 1)[0]
    assert 'default=True' in dashboard
    assert text.index('pages/dashboard.py') < text.index('pages/watchlist.py')


def test_daily_workflow_precedes_advanced_research():
    text = (ROOT / "app.py").read_text()
    assert text.index('pages/watchlist.py') < text.index('pages/research_lab.py')
    assert text.index('pages/trade_planner.py') < text.index('pages/research_lab.py')
    assert text.index('pages/research_lab.py') < text.index('pages/datenmodell.py')
