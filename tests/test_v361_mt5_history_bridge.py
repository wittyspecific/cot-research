from pathlib import Path


def test_bridge_contains_read_only_history_request_service():
    root = Path(__file__).resolve().parents[1]
    source = (root / "mt5" / "MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")
    assert "CopyRates(" in source
    assert 'cot_history_request_*.csv' in source
    assert 'cot_history_response_' in source
    assert "PERIOD_M5" in source
    assert "PERIOD_H1" in source
    assert "PERIOD_M1" in source
    forbidden = ["OrderSend(", "trade.Buy(", "trade.Sell(", "PositionClose(", "PositionModify("]
    for token in forbidden:
        assert token not in source


def test_python_bridge_protocol_reads_history_response(tmp_path):
    import threading, time
    import pandas as pd
    from src.mt5_account import MT5Config
    from src.mt5_history import HistoryRequest, bridge_history_batch

    # Discovery requires the normal live-bridge heartbeat files to exist.
    (tmp_path / "cot_mt5_account.csv").write_text("x\n1\n", encoding="utf-8")
    (tmp_path / "cot_mt5_positions.csv").write_text("x\n", encoding="utf-8")
    req = HistoryRequest("XAUUSD", "2026-08-16T10:00:00Z", "2026-08-16T10:10:00Z", "M5", "abc123")

    def responder():
        request_path = tmp_path / "cot_history_request_abc123.csv"
        for _ in range(100):
            if request_path.exists():
                break
            time.sleep(0.01)
        response = tmp_path / "cot_history_response_abc123.csv"
        pd.DataFrame([{
            "request_id": "abc123", "status": "OK", "error": "", "time_unix": 1786874400,
            "open": 100, "high": 102, "low": 99, "close": 101, "tick_volume": 1, "spread": 2, "real_volume": 0,
        }]).to_csv(response, sep=";", index=False)

    thread = threading.Thread(target=responder, daemon=True)
    thread.start()
    result = bridge_history_batch(MT5Config(mode="bridge", bridge_common_path=str(tmp_path)), [req], timeout_seconds=2)
    thread.join(timeout=1)
    assert len(result["abc123"]) == 1
    assert result["abc123"].iloc[0]["close"] == 101
