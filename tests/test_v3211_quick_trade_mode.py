
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "pages" / "trade_planner.py"


def _text():
    return PLANNER.read_text(encoding="utf-8")


def test_quick_trade_mode_is_primary():
    text = _text()
    assert "V3.21.1 · QUICK TRADE MODE" in text
    assert 'st.markdown("### Trade Setup")' in text
    assert 'q1, q2, q3, q4 = st.columns' in text


def test_secondary_setup_is_collapsed():
    text = _text()
    expander = text.index('with st.expander("Weitere Setup-Details (optional)"')
    for token in (
        '"Zone"',
        '"Freshness"',
        '"Eigene Zonenqualität"',
        '"Zone Low"',
        '"Zone High"',
        '"Retest-Anzahl"',
        '"Limit gültig (Kalendertage)"',
        '"Grund falls SKIPPED"',
        '"Notiz"',
    ):
        assert text.index(token) > expander, token


def test_primary_controls_are_before_optional_expander():
    text = _text()
    expander = text.index('with st.expander("Weitere Setup-Details (optional)"')
    assert text.index('"Entry"') < expander
    assert text.index('"Stop"') < expander
    assert text.index('v3211_target_mode') < expander
    assert text.index('"Gewünschtes Risiko (%)"') < expander


def test_compact_target_modes_exist():
    text = _text()
    assert '["2R", "2.5R", "3R", "MANUELL", "KEIN TP"]' in text
    assert 'use_target = v3211_target_mode != "KEIN TP"' in text


def test_save_and_market_fill_contracts_survive():
    text = _text()
    assert 'plan["entry"] = auto_market_reference_entry(plan)' in text
    assert 'plan["market_entry_auto"] = True' in text
    assert "payload = collect_trade_snapshot(" in text
    assert "create_trade_plan" in text


def test_big_stepper_is_not_executable():
    text = _text()
    tree = ast.parse(text)
    executable = "\n".join(
        ast.get_source_segment(text, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )
    assert "v3210-stepper" not in executable


def test_planner_parses():
    ast.parse(_text(), filename=str(PLANNER))
