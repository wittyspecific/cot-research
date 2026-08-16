from pathlib import Path


def test_trading_section_contains_planner_and_journal():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"TRADING": [' in app
    assert 'pages/trade_planner.py' in app
    assert 'pages/trading_journal.py' in app
    assert app.index('"TRADING": [') < app.index('"MARKT & PORTFOLIO": [')
