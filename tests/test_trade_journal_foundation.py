from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.trade_journal import (
    append_trade_event,
    create_trade_plan,
    flatten_snapshot,
    get_trade_events,
    get_trade_snapshot,
    initialize_journal,
    journal_connection,
    list_trade_plans,
    upsert_trade_outcome,
)
from src.trade_context import infer_cot_context


def _plan(**updates):
    base = {
        "plan_type": "SIMULATION",
        "skip_reason": "",
        "asset_class": "Metals",
        "market_name": "Gold",
        "cot_symbol": "GC",
        "cftc_code": "088691",
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "zone_type": "DEMAND",
        "timeframe": "4H",
        "zone_low": 3290.0,
        "zone_high": 3305.0,
        "entry": 3300.0,
        "stop": 3280.0,
        "target": 3380.0,
        "requested_risk_pct": 0.0025,
        "zone_freshness": "FRESH",
        "retest_count": 0,
        "quality_grade": "A",
        "notes": "test",
    }
    base.update(updates)
    return base


def _snapshot():
    return {
        "cot": {
            "commercial_percentile": 94.2,
            "nc_percentile": 7.8,
            "retail_percentile": 13.1,
            "confirmed": True,
        },
        "seasonality": {"20d_median": 0.021, "support": "SUPPORT"},
        "risk": {"status": "GREEN", "open_risk": 0.012},
    }


def test_schema_and_plan_snapshot_are_created_atomically(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    plans = list_trade_plans(db_path=db)
    assert len(plans) == 1
    assert plans.iloc[0]["trade_id"] == saved["trade_id"]
    snap = get_trade_snapshot(saved["trade_id"], db_path=db)
    assert snap["cot"]["commercial_percentile"] == 94.2
    assert snap["plan"]["cfd_symbol"] == "XAUUSD"
    assert saved["feature_count"] >= 10


def test_snapshot_hash_detects_manual_tampering(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    # Deliberately bypass the immutable trigger to simulate file-level corruption.
    with sqlite3.connect(db) as con:
        con.execute("DROP TRIGGER no_update_trade_snapshots")
        con.execute("UPDATE trade_snapshots SET payload_json='{}' WHERE trade_id=?", (saved["trade_id"],))
        con.commit()
    with pytest.raises(RuntimeError, match="Hash"):
        get_trade_snapshot(saved["trade_id"], db_path=db)


def test_plan_and_snapshot_are_immutable(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    with journal_connection(db) as con:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute("UPDATE trade_plans SET entry=1 WHERE trade_id=?", (saved["trade_id"],))
    with journal_connection(db) as con:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute("DELETE FROM trade_snapshots WHERE trade_id=?", (saved["trade_id"],))


def test_events_are_append_only(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    append_trade_event(saved["trade_id"], "STOP_CHANGED", {"old": 3280, "new": 3290}, db_path=db)
    events = get_trade_events(saved["trade_id"], db_path=db)
    assert list(events["event_type"]) == ["PLAN_CREATED", "STOP_CHANGED"]
    with journal_connection(db) as con:
        event_id = events.iloc[-1]["event_id"]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            con.execute("UPDATE trade_events SET event_type='X' WHERE event_id=?", (event_id,))


def test_outcomes_are_mutable_derived_data(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    upsert_trade_outcome(saved["trade_id"], {"entry_triggered": 1, "mfe_r": 1.2, "mae_r": -0.3}, db_path=db)
    upsert_trade_outcome(saved["trade_id"], {"entry_triggered": 1, "mfe_r": 2.4, "mae_r": -0.3, "result_r": 2.0}, db_path=db)
    plans = list_trade_plans(db_path=db)
    assert plans.iloc[0]["mfe_r"] == pytest.approx(2.4)
    assert plans.iloc[0]["result_r"] == pytest.approx(2.0)


def test_flatten_snapshot_preserves_numeric_bool_and_list_data():
    rows = flatten_snapshot({
        "cot": {"pct": np.float64(91.2), "ok": np.bool_(True)},
        "portfolio": {"positions": [{"symbol": "XAUUSD"}]},
    })
    lookup = {(r["feature_group"], r["feature_name"]): r for r in rows}
    assert lookup[("cot", "pct")]["numeric_value"] == pytest.approx(91.2)
    assert lookup[("cot", "ok")]["bool_value"] == 1
    assert "XAUUSD" in lookup[("portfolio", "positions")]["text_value"]


def test_fx_pair_context_is_inferred_from_symbol_spec():
    ctx = infer_cot_context("AUDJPY", {"currency_base": "AUD", "currency_profit": "JPY"})
    assert ctx == {"mode": "FX_PAIR", "base": "AUD", "quote": "JPY"}


def test_copper_cfd_maps_to_copper_cot_market():
    ctx = infer_cot_context("XCUUSD", {})
    assert ctx["mode"] == "MARKET"
    assert ctx["market"]["symbol"] == "HG"
    assert ctx["asset_class"] == "Metals"


def test_skipped_plan_without_reason_records_explicit_missing_reason(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(plan_type="SKIPPED", skip_reason=""), snapshot_payload=_snapshot(), db_path=db)
    plans = list_trade_plans(db_path=db)
    assert plans.iloc[0]["skip_reason"] == "NICHT ANGEGEBEN"
    assert saved["plan"]["plan_type"] == "SKIPPED"


def test_feature_matrix_keeps_plan_features_and_outcome_labels_separate(tmp_path: Path):
    from src.trade_journal import build_feature_matrix
    db = tmp_path / "journal.sqlite3"
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), db_path=db)
    upsert_trade_outcome(saved["trade_id"], {"result_r": 1.5, "mfe_r": 2.0}, db_path=db)
    matrix = build_feature_matrix(db_path=db, include_text=False, include_outcomes=True)
    assert len(matrix) == 1
    assert "feature__cot__commercial_percentile" in matrix.columns
    assert matrix.iloc[0]["feature__cot__commercial_percentile"] == pytest.approx(94.2)
    assert "label__result_r" in matrix.columns
    assert matrix.iloc[0]["label__result_r"] == pytest.approx(1.5)
