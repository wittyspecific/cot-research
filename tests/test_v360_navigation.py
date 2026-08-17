from pathlib import Path


def test_trading_section_contains_simple_daily_flow():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"TRADING": [' in app
    assert 'pages/trade_planner.py' in app
    assert 'pages/trading_journal.py' in app
    assert 'pages/prop_desk.py' in app
    assert app.index('"RESEARCH": [') < app.index('"TRADING": [') < app.index('"ADVANCED": [')
