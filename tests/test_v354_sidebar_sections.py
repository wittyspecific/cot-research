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

    dashboard = (
        text.split('"pages/dashboard.py"', 1)[1]
        .split('),', 1)[0]
    )

    assert "default=True" in dashboard

    # V3.29.x: Watchlist is integrated into Opportunity Scanner.
    assert text.index("pages/dashboard.py") < text.index(
        "pages/opportunity_scanner.py"
    )

    assert 'title="Opportunity Scanner"' in text


def test_daily_workflow_precedes_advanced_research():
    text = (ROOT / "app.py").read_text()

    # V3.29.x daily research workflow starts with Opportunity Scanner.
    scanner = text.index("pages/opportunity_scanner.py")

    # Existing Advanced / research-lab functionality remains later in the
    # navigation source when present.
    if "pages/research_lab.py" in text:
        assert scanner < text.index("pages/research_lab.py")
    else:
        assert '"ADVANCED"' in text
        assert scanner < text.index('"ADVANCED"')
