
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "pages" / "trade_planner.py"


def _text():
    return PLANNER.read_text(encoding="utf-8")


def test_trade_ticket_preview_is_present():
    text = _text()
    assert "V3.21.0 · TRADE TICKET UX PREVIEW" in text
    assert "Asset & Richtung" in text
    assert "Review & Speichern" in text
    assert "Trade Ticket · Live" in text


def test_fixed_rr_target_presets_are_present():
    text = _text()
    assert "Target-Vorlage" in text
    assert '"2R"' in text
    assert '"2.5R"' in text
    assert '"3R"' in text
    assert '"MANUELL"' in text


def test_market_entry_contract_is_unchanged():
    text = _text()
    assert 'value="AUTO · nächster Ask" if side == "LONG" else "AUTO · nächster Bid"' in text
    assert 'plan["entry"] = auto_market_reference_entry(plan)' in text
    assert 'plan["market_entry_auto"] = True' in text


def test_snapshot_and_save_pipeline_still_exists():
    text = _text()
    assert "payload = collect_trade_snapshot(" in text
    assert "create_trade_plan" in text
    assert '"Trade speichern"' in text
    assert '"Gewünschtes Risiko (%)"' in text


def test_new_ticket_is_display_only():
    text = _text()
    assert "Display-only ticket. It does not alter plan, snapshot, sizing or execution." in text


def test_planner_parses():
    ast.parse(_text(), filename=str(PLANNER))
