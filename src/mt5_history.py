from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import os
from pathlib import Path
import time
from typing import Any, Iterable, Mapping
import uuid

import pandas as pd

from .mt5_account import (
    MT5BridgeError,
    MT5Config,
    MT5ConnectionError,
    discover_bridge_directory,
    mt5_python_available,
)


SUPPORTED_TIMEFRAMES = {"M1", "M5", "H1", "D1"}
BAR_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]


class MT5HistoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoryRequest:
    symbol: str
    start_utc: datetime | pd.Timestamp
    end_utc: datetime | pd.Timestamp
    timeframe: str = "M5"
    request_id: str = ""

    def normalized(self) -> "HistoryRequest":
        tf = str(self.timeframe or "M5").upper()
        if tf not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Nicht unterstützter MT5-Timeframe: {tf}")
        symbol = str(self.symbol or "").strip()
        if not symbol:
            raise ValueError("HistoryRequest benötigt ein Symbol.")
        start = _utc_timestamp(self.start_utc)
        end = _utc_timestamp(self.end_utc)
        if end <= start:
            raise ValueError("HistoryRequest end_utc muss nach start_utc liegen.")
        return HistoryRequest(
            symbol=symbol,
            start_utc=start,
            end_utc=end,
            timeframe=tf,
            request_id=self.request_id or uuid.uuid4().hex,
        )


def _utc_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame(columns=BAR_COLUMNS)


def _normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return _empty_bars()
    out = df.copy()
    for col in BAR_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    if "time_unix" in out.columns and "time" not in df.columns:
        out["time"] = pd.to_datetime(out["time_unix"], unit="s", utc=True, errors="coerce")
    else:
        out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["time", "open", "high", "low", "close"])
    out = out.sort_values("time").drop_duplicates(subset=["time"], keep="last")
    return out[BAR_COLUMNS].reset_index(drop=True)


def _write_request_file(directory: Path, request: HistoryRequest) -> Path:
    final = directory / f"cot_history_request_{request.request_id}.csv"
    temp = directory / f".cot_history_request_{request.request_id}.tmp"
    row = pd.DataFrame([{
        "request_id": request.request_id,
        "symbol": request.symbol,
        "from_unix": int(_utc_timestamp(request.start_utc).timestamp()),
        "to_unix": int(_utc_timestamp(request.end_utc).timestamp()),
        "timeframe": request.timeframe,
    }])
    row.to_csv(temp, sep=";", index=False, encoding="utf-8")
    os.replace(temp, final)
    return final


def _read_response(path: Path, request: HistoryRequest) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="cp1252")
    if df.empty:
        return _empty_bars()
    status = str(df.iloc[0].get("status", "OK") or "OK").upper()
    error = str(df.iloc[0].get("error", "") or "")
    if status != "OK":
        raise MT5HistoryError(f"MT5-Historie {request.symbol} {request.timeframe}: {error or status}")
    return _normalize_bars(df)


def bridge_history_batch(
    config: MT5Config,
    requests: Iterable[HistoryRequest],
    *,
    timeout_seconds: float = 10.0,
    poll_seconds: float = 0.15,
) -> dict[str, pd.DataFrame]:
    normalized = [request.normalized() for request in requests]
    if not normalized:
        return {}
    directory = discover_bridge_directory(config.bridge_common_path)
    if directory is None:
        raise MT5BridgeError("MT5 Common\\Files-Ordner für History-Bridge nicht gefunden.")

    pending: dict[str, tuple[HistoryRequest, Path, Path]] = {}
    for req in normalized:
        response = directory / f"cot_history_response_{req.request_id}.csv"
        request_path = directory / f"cot_history_request_{req.request_id}.csv"
        for stale in (response, request_path):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                pass
        _write_request_file(directory, req)
        pending[req.request_id] = (req, request_path, response)

    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    while time.monotonic() < deadline:
        if all(response.exists() for _, _, response in pending.values()):
            break
        time.sleep(max(0.05, float(poll_seconds)))

    missing = [req.symbol for req, _, response in pending.values() if not response.exists()]
    if missing:
        for _, request_path, response in pending.values():
            try:
                request_path.unlink(missing_ok=True)
                response.unlink(missing_ok=True)
            except OSError:
                pass
        raise MT5HistoryError(
            "MT5-History-Bridge antwortet nicht rechtzeitig für: " + ", ".join(sorted(set(missing)))
        )

    results: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for request_id, (req, request_path, response) in pending.items():
        try:
            results[request_id] = _read_response(response, req)
        except Exception as exc:
            errors.append(str(exc))
            results[request_id] = _empty_bars()
        finally:
            for path in (request_path, response):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
    if errors:
        raise MT5HistoryError(" | ".join(errors))
    return results


def _direct_timeframe(mt5: Any, timeframe: str) -> Any:
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "H1": mt5.TIMEFRAME_H1,
        "D1": mt5.TIMEFRAME_D1,
    }[timeframe]


def direct_history_batch(config: MT5Config, requests: Iterable[HistoryRequest]) -> dict[str, pd.DataFrame]:
    normalized = [request.normalized() for request in requests]
    if not normalized:
        return {}
    if not config.has_credentials:
        raise MT5ConnectionError("Direkte MT5-Historie benötigt Login, Passwort und Server.")
    if not mt5_python_available():
        raise MT5ConnectionError("MetaTrader5-Pythonmodul ist nicht verfügbar.")
    mt5 = importlib.import_module("MetaTrader5")
    kwargs = {
        "login": config.login,
        "password": config.password,
        "server": config.server,
        "timeout": config.timeout_ms,
    }
    if config.terminal_path:
        ok = mt5.initialize(config.terminal_path, **kwargs)
    else:
        ok = mt5.initialize(**kwargs)
    if not ok:
        raise MT5ConnectionError(f"MT5 initialize() für History fehlgeschlagen: {mt5.last_error()}")
    try:
        results: dict[str, pd.DataFrame] = {}
        for req in normalized:
            rates = mt5.copy_rates_range(
                req.symbol,
                _direct_timeframe(mt5, req.timeframe),
                _utc_timestamp(req.start_utc).to_pydatetime(),
                _utc_timestamp(req.end_utc).to_pydatetime(),
            )
            results[req.request_id] = _normalize_bars(pd.DataFrame(rates) if rates is not None else pd.DataFrame())
        return results
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def history_batch(
    config: MT5Config,
    requests: Iterable[HistoryRequest],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, pd.DataFrame]:
    requests = list(requests)
    if config.mode == "python":
        return direct_history_batch(config, requests)
    if config.mode == "bridge":
        return bridge_history_batch(config, requests, timeout_seconds=timeout_seconds)
    if config.has_credentials and mt5_python_available():
        try:
            return direct_history_batch(config, requests)
        except Exception:
            pass
    return bridge_history_batch(config, requests, timeout_seconds=timeout_seconds)
