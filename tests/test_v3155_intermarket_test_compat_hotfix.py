from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "intermarket.py"


def test_v3154_source_contract_names_are_preserved():
    text = ENGINE.read_text(encoding="utf-8")
    assert 'currency_decision.get("macro")' in text
    assert 'currency_decision.get("micro")' in text
    assert 'reference_decision.get("macro")' in text
    assert 'reference_decision.get("micro")' in text


def test_current_decision_core_is_still_used():
    text = ENGINE.read_text(encoding="utf-8")
    assert "classify_macro_micro_trade(left_row)" in text
    assert "classify_macro_micro_trade(right_row)" in text


def test_expanded_universe_remains():
    text = ENGINE.read_text(encoding="utf-8")
    assert "INTERMARKET_RELATIONSHIPS" in text
    assert "CORE_RELATIONSHIPS" in text


def test_engine_parses():
    ast.parse(ENGINE.read_text(encoding="utf-8"))
