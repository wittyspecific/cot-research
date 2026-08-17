from pathlib import Path


def test_market_planner_injects_schema_reference_before_snapshot():
    src = (Path(__file__).resolve().parents[1] / 'pages' / 'trade_planner.py').read_text()
    assert 'plan["entry"] = auto_market_reference_entry(plan)' in src
    assert 'plan["market_entry_auto"] = True' in src
    assert src.index('plan["entry"] = auto_market_reference_entry(plan)') < src.index('payload = collect_trade_snapshot(')
