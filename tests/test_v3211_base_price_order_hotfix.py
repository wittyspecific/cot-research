from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "pages" / "trade_planner.py"


def test_pricing_init_precedes_quick_setup():
    text = PLANNER.read_text(encoding="utf-8")
    marker = "# V3.21.1 · QUICK SETUP PRICING INIT HOTFIX"
    quick = 'st.markdown("### Trade Setup")'
    assert marker in text
    assert text.index(marker) < text.index(quick)

    tree = ast.parse(text)
    quick_line = text[:text.index(quick)].count("\n") + 1

    top_level_before = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.lineno < quick_line:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    top_level_before.add(target.id)

    assert "base_price" in top_level_before
    assert "step" in top_level_before


def test_market_and_snapshot_contracts_survive():
    text = PLANNER.read_text(encoding="utf-8")
    assert 'plan["entry"] = auto_market_reference_entry(plan)' in text
    assert 'plan["market_entry_auto"] = True' in text
    assert "payload = collect_trade_snapshot(" in text
    assert "create_trade_plan" in text


def test_quick_mode_survives():
    text = PLANNER.read_text(encoding="utf-8")
    assert 'st.markdown("### Trade Setup")' in text
    assert 'with st.expander("Weitere Setup-Details (optional)"' in text
    assert '["2R", "2.5R", "3R", "MANUELL", "KEIN TP"]' in text


def test_planner_parses():
    ast.parse(
        PLANNER.read_text(encoding="utf-8"),
        filename=str(PLANNER),
    )
