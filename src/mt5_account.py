from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import os
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pandas as pd


ACCOUNT_COLUMNS = [
    "timestamp_unix",
    "login",
    "server",
    "name",
    "company",
    "currency",
    "balance",
    "equity",
    "profit",
    "margin",
    "margin_free",
    "margin_level",
    "leverage",
    "trade_allowed",
    "trade_expert",
    "day_start_balance",
    "daily_realized_pnl",
    "server_time_unix",
]

POSITION_COLUMNS = [
    "ticket",
    "symbol",
    "side",
    "volume",
    "price_open",
    "sl",
    "tp",
    "price_current",
    "profit",
    "swap",
    "time",
    "comment",
    "contract_size",
    "tick_size",
    "tick_value",
    "tick_value_profit",
    "tick_value_loss",
    "point",
    "digits",
    "volume_min",
    "volume_max",
    "volume_step",
    "currency_base",
    "currency_profit",
    "currency_margin",
    "swap_long",
    "swap_short",
]


class MT5Error(RuntimeError):
    """Base exception for the read-only MT5 adapter."""


class MT5ConfigError(MT5Error):
    pass


class MT5UnavailableError(MT5Error):
    pass


class MT5ConnectionError(MT5Error):
    pass


class MT5BridgeError(MT5Error):
    pass


@dataclass(frozen=True)
class MT5Config:
    mode: str = "auto"
    login: int | None = None
    password: str = ""
    server: str = ""
    terminal_path: str = ""
    timeout_ms: int = 10_000
    bridge_common_path: str = ""
    bridge_max_age_seconds: int = 15

    @property
    def has_credentials(self) -> bool:
        return bool(self.login and self.password and self.server)


def _as_plain_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return {}


def config_from_mapping(mapping: Mapping[str, Any] | None) -> MT5Config:
    raw = _as_plain_mapping(mapping)
    login_value = raw.get("login")
    login = None
    if login_value not in (None, ""):
        try:
            login = int(login_value)
        except (TypeError, ValueError) as exc:
            raise MT5ConfigError("MT5 login muss eine Kontonummer sein.") from exc

    mode = str(raw.get("mode", "auto") or "auto").strip().lower()
    if mode not in {"auto", "python", "bridge"}:
        raise MT5ConfigError("MT5 mode muss auto, python oder bridge sein.")

    return MT5Config(
        mode=mode,
        login=login,
        password=str(raw.get("password", "") or ""),
        server=str(raw.get("server", "") or ""),
        terminal_path=str(raw.get("terminal_path", "") or ""),
        timeout_ms=max(1_000, int(raw.get("timeout_ms", 10_000) or 10_000)),
        bridge_common_path=str(raw.get("bridge_common_path", "") or ""),
        bridge_max_age_seconds=max(
            3,
            int(raw.get("bridge_max_age_seconds", 15) or 15),
        ),
    )


def mt5_python_available() -> bool:
    try:
        return importlib.util.find_spec("MetaTrader5") is not None
    except (ImportError, AttributeError, ValueError):
        return False


def runtime_diagnostics() -> dict[str, Any]:
    return {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "mt5_python_available": mt5_python_available(),
    }


def _last_error_text(mt5: Any) -> str:
    try:
        err = mt5.last_error()
    except Exception:
        return "unbekannter MT5-Fehler"
    if isinstance(err, tuple) and len(err) >= 2:
        return f"{err[0]} · {err[1]}"
    return str(err)


def _namedtuple_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "_asdict"):
        return dict(value._asdict())
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key, None))
    }


def _finite_or_nan(value: Any) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return np.nan
    return val if np.isfinite(val) else np.nan


def _unix_to_timestamp(value: Any) -> pd.Timestamp:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return pd.NaT
    if ivalue <= 0:
        return pd.NaT
    return pd.to_datetime(ivalue, unit="s", utc=True).tz_convert(None)


def _position_side(mt5: Any, raw_type: Any) -> str:
    try:
        value = int(raw_type)
    except (TypeError, ValueError):
        return "—"
    buy = int(getattr(mt5, "POSITION_TYPE_BUY", 0))
    sell = int(getattr(mt5, "POSITION_TYPE_SELL", 1))
    if value == buy:
        return "LONG"
    if value == sell:
        return "SHORT"
    return str(value)


def _account_snapshot(account_raw: Any) -> dict[str, Any]:
    a = _namedtuple_dict(account_raw)
    return {
        "login": int(a["login"]) if a.get("login") is not None else None,
        "server": str(a.get("server", "") or ""),
        "name": str(a.get("name", "") or ""),
        "company": str(a.get("company", "") or ""),
        "currency": str(a.get("currency", "") or ""),
        "balance": _finite_or_nan(a.get("balance")),
        "equity": _finite_or_nan(a.get("equity")),
        "profit": _finite_or_nan(a.get("profit")),
        "margin": _finite_or_nan(a.get("margin")),
        "margin_free": _finite_or_nan(a.get("margin_free")),
        "margin_level": _finite_or_nan(a.get("margin_level")),
        "leverage": int(a.get("leverage", 0) or 0),
        "trade_allowed": bool(a.get("trade_allowed", False)),
        "trade_expert": bool(a.get("trade_expert", False)),
        "trade_mode": a.get("trade_mode"),
        "day_start_balance": _finite_or_nan(a.get("day_start_balance")),
        "daily_realized_pnl": _finite_or_nan(a.get("daily_realized_pnl")),
        "server_time_unix": _finite_or_nan(a.get("server_time_unix")),
    }


def _symbol_snapshot_from_mapping(mt5: Any, symbol: str, s: Mapping[str, Any]) -> dict[str, Any]:
    trade_mode = s.get("trade_mode")
    try:
        trade_mode_int = int(trade_mode)
    except (TypeError, ValueError):
        trade_mode_int = None
    disabled = int(getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0))
    close_only = int(getattr(mt5, "SYMBOL_TRADE_MODE_CLOSEONLY", 3))
    can_open = trade_mode_int not in {disabled, close_only} if trade_mode_int is not None else True
    return {
        "symbol": symbol,
        "description": str(s.get("description", "") or ""),
        "path": str(s.get("path", "") or ""),
        "selected": bool(s.get("select", s.get("selected", False))),
        "visible": bool(s.get("visible", False)),
        "trade_mode": trade_mode_int,
        "can_open": can_open,
        "bid": _finite_or_nan(s.get("bid")),
        "ask": _finite_or_nan(s.get("ask")),
        "last": _finite_or_nan(s.get("last")),
        "contract_size": _finite_or_nan(s.get("trade_contract_size")),
        "tick_size": _finite_or_nan(s.get("trade_tick_size")),
        "tick_value": _finite_or_nan(s.get("trade_tick_value")),
        "tick_value_profit": _finite_or_nan(s.get("trade_tick_value_profit")),
        "tick_value_loss": _finite_or_nan(s.get("trade_tick_value_loss")),
        "point": _finite_or_nan(s.get("point")),
        "digits": int(s.get("digits", 0) or 0),
        "volume_min": _finite_or_nan(s.get("volume_min")),
        "volume_max": _finite_or_nan(s.get("volume_max")),
        "volume_step": _finite_or_nan(s.get("volume_step")),
        "currency_base": str(s.get("currency_base", "") or ""),
        "currency_profit": str(s.get("currency_profit", "") or ""),
        "currency_margin": str(s.get("currency_margin", "") or ""),
        "swap_long": _finite_or_nan(s.get("swap_long")),
        "swap_short": _finite_or_nan(s.get("swap_short")),
        "margin_initial": _finite_or_nan(s.get("margin_initial")),
        "margin_maintenance": _finite_or_nan(s.get("margin_maintenance")),
        "trade_calc_mode": s.get("trade_calc_mode"),
    }


def _symbol_snapshot(mt5: Any, symbol: str) -> dict[str, Any]:
    info = mt5.symbol_info(symbol)
    return _symbol_snapshot_from_mapping(mt5, symbol, _namedtuple_dict(info))


def _full_symbol_catalog(mt5: Any, fallback_specs: pd.DataFrame) -> pd.DataFrame:
    """Read the complete broker symbol universe when the Python API exposes it."""
    getter = getattr(mt5, "symbols_get", None)
    if getter is None:
        return fallback_specs.copy()
    try:
        raw = getter()
    except Exception:
        raw = None
    if not raw:
        return fallback_specs.copy()

    rows: list[dict[str, Any]] = []
    for item in raw:
        mapping = _namedtuple_dict(item)
        symbol = str(mapping.get("name", "") or "")
        if not symbol:
            continue
        rows.append(_symbol_snapshot_from_mapping(mt5, symbol, mapping))
    catalog = pd.DataFrame(rows)
    return catalog.drop_duplicates(subset=["symbol"]).reset_index(drop=True) if not catalog.empty else fallback_specs.copy()


def _positions_snapshot(mt5: Any, positions_raw: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    specs: dict[str, dict[str, Any]] = {}

    for item in positions_raw or ():
        p = _namedtuple_dict(item)
        symbol = str(p.get("symbol", "") or "")
        if symbol and symbol not in specs:
            try:
                specs[symbol] = _symbol_snapshot(mt5, symbol)
            except Exception:
                specs[symbol] = {"symbol": symbol}

        spec = specs.get(symbol, {})
        rows.append({
            "ticket": int(p.get("ticket", 0) or 0),
            "symbol": symbol,
            "side": _position_side(mt5, p.get("type")),
            "volume": _finite_or_nan(p.get("volume")),
            "price_open": _finite_or_nan(p.get("price_open")),
            "sl": _finite_or_nan(p.get("sl")),
            "tp": _finite_or_nan(p.get("tp")),
            "price_current": _finite_or_nan(p.get("price_current")),
            "profit": _finite_or_nan(p.get("profit")),
            "swap": _finite_or_nan(p.get("swap")),
            "time": _unix_to_timestamp(p.get("time")),
            "comment": str(p.get("comment", "") or ""),
            **{key: spec.get(key, np.nan) for key in POSITION_COLUMNS if key in spec},
        })

    positions = pd.DataFrame(rows)
    if positions.empty:
        positions = pd.DataFrame(columns=POSITION_COLUMNS)
    else:
        for col in POSITION_COLUMNS:
            if col not in positions.columns:
                positions[col] = np.nan
        positions = positions[POSITION_COLUMNS]

    specs_df = pd.DataFrame(list(specs.values()))
    return positions, specs_df


def direct_snapshot(config: MT5Config, mt5_module: Any | None = None) -> dict[str, Any]:
    """Read one account snapshot through the official MetaTrader5 Python API.

    This module deliberately exposes no order-send, close-position, SL/TP-change
    or other trading function. It only initializes the terminal connection and
    reads account, position and symbol information.
    """
    if not config.has_credentials:
        raise MT5ConfigError(
            "Für den direkten MT5-Modus fehlen login, password oder server."
        )

    if mt5_module is None:
        try:
            mt5_module = importlib.import_module("MetaTrader5")
        except ImportError as exc:
            raise MT5UnavailableError(
                "Das MetaTrader5-Pythonmodul ist in dieser Python-Umgebung nicht verfügbar."
            ) from exc

    mt5 = mt5_module
    kwargs: dict[str, Any] = {
        "login": int(config.login),
        "password": config.password,
        "server": config.server,
        "timeout": int(config.timeout_ms),
    }

    initialized = False
    try:
        if config.terminal_path:
            initialized = bool(mt5.initialize(config.terminal_path, **kwargs))
        else:
            initialized = bool(mt5.initialize(**kwargs))

        if not initialized:
            raise MT5ConnectionError(
                "MT5 initialize() fehlgeschlagen: " + _last_error_text(mt5)
            )

        account_raw = mt5.account_info()
        if account_raw is None:
            raise MT5ConnectionError(
                "MT5 account_info() fehlgeschlagen: " + _last_error_text(mt5)
            )
        account = _account_snapshot(account_raw)

        if account.get("login") and int(account["login"]) != int(config.login):
            raise MT5ConnectionError(
                "Das verbundene MT5-Terminal meldet eine andere Kontonummer als konfiguriert."
            )

        positions_raw = mt5.positions_get()
        if positions_raw is None:
            raise MT5ConnectionError(
                "MT5 positions_get() fehlgeschlagen: " + _last_error_text(mt5)
            )
        positions, specs = _positions_snapshot(mt5, positions_raw)
        catalog = _full_symbol_catalog(mt5, specs)

        try:
            terminal_version = mt5.version()
        except Exception:
            terminal_version = None

        return {
            "source": "MT5 PYTHON · READ ONLY",
            "captured_at": pd.Timestamp.now(tz="UTC").tz_convert(None),
            "account": account,
            "positions": positions,
            "symbol_specs": specs,
            "symbol_catalog": catalog,
            "terminal_version": terminal_version,
            "warnings": [],
        }
    finally:
        if initialized:
            try:
                mt5.shutdown()
            except Exception:
                pass


def _bridge_candidates(explicit_dir: str = "") -> list[Path]:
    candidates: list[Path] = []
    if explicit_dir:
        candidates.append(Path(explicit_dir).expanduser())
    env_path = os.getenv("MT5_COMMON_FILES", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    home = Path.home()
    mac_roots = [
        home / "Library/Application Support/net.metaquotes.wine.metatrader5",
        home / "Library/Application Support/Metatrader 5",
    ]
    for root in mac_roots:
        if not root.exists():
            continue
        try:
            for account_file in root.rglob("cot_mt5_account.csv"):
                candidates.append(account_file.parent)
        except (OSError, PermissionError):
            pass

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def discover_bridge_directory(explicit_dir: str = "") -> Path | None:
    for directory in _bridge_candidates(explicit_dir):
        if (
            (directory / "cot_mt5_account.csv").exists()
            and (directory / "cot_mt5_positions.csv").exists()
        ):
            return directory
    return None


def _read_bridge_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", encoding="cp1252")
    except Exception as exc:
        raise MT5BridgeError(f"Bridge-Datei konnte nicht gelesen werden: {path.name}") from exc


def _bool_value(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "ja"}


def bridge_snapshot(config: MT5Config) -> dict[str, Any]:
    directory = discover_bridge_directory(config.bridge_common_path)
    if directory is None:
        raise MT5BridgeError(
            "Keine MT5-Bridge-Dateien gefunden. MT5ReadOnlyBridge.mq5 muss in MT5 laufen "
            "oder bridge_common_path muss auf den Common\\Files-Ordner zeigen."
        )

    account_path = directory / "cot_mt5_account.csv"
    positions_path = directory / "cot_mt5_positions.csv"
    account_df = _read_bridge_csv(account_path)
    positions_df = _read_bridge_csv(positions_path)
    symbols_path = directory / "cot_mt5_symbols.csv"
    symbols_df = _read_bridge_csv(symbols_path) if symbols_path.exists() else pd.DataFrame()
    if account_df.empty:
        raise MT5BridgeError("Die MT5-Account-Bridge-Datei ist leer.")

    row = account_df.iloc[-1]

    # TimeCurrent() in MT5 represents the last known trade-server time and can
    # remain unchanged while markets are closed (e.g. weekends). Therefore it
    # must not be used as the bridge heartbeat. Freshness is based on the local
    # CSV modification times, which advance every time the EA exports a snapshot.
    market_time = _unix_to_timestamp(row.get("timestamp_unix", np.nan))
    account_updated_at = pd.Timestamp.fromtimestamp(
        account_path.stat().st_mtime, tz=timezone.utc
    ).tz_convert(None)
    positions_updated_at = pd.Timestamp.fromtimestamp(
        positions_path.stat().st_mtime, tz=timezone.utc
    ).tz_convert(None)
    captured_at = min(account_updated_at, positions_updated_at)

    age_seconds = (
        pd.Timestamp.now(tz="UTC").tz_convert(None) - pd.Timestamp(captured_at)
    ).total_seconds()
    if age_seconds > int(config.bridge_max_age_seconds):
        raise MT5BridgeError(
            f"MT5-Bridge ist veraltet ({age_seconds:.0f}s). EA/Terminal prüfen."
        )

    account = {
        "login": int(row["login"]) if pd.notna(row.get("login")) else None,
        "server": str(row.get("server", "") or ""),
        "name": str(row.get("name", "") or ""),
        "company": str(row.get("company", "") or ""),
        "currency": str(row.get("currency", "") or ""),
        "balance": _finite_or_nan(row.get("balance")),
        "equity": _finite_or_nan(row.get("equity")),
        "profit": _finite_or_nan(row.get("profit")),
        "margin": _finite_or_nan(row.get("margin")),
        "margin_free": _finite_or_nan(row.get("margin_free")),
        "margin_level": _finite_or_nan(row.get("margin_level")),
        "leverage": int(row.get("leverage", 0) or 0),
        "trade_allowed": _bool_value(row.get("trade_allowed", False)),
        "trade_expert": _bool_value(row.get("trade_expert", False)),
        "trade_mode": None,
        "day_start_balance": _finite_or_nan(row.get("day_start_balance")),
        "daily_realized_pnl": _finite_or_nan(row.get("daily_realized_pnl")),
        "server_time_unix": _finite_or_nan(row.get("server_time_unix")),
    }

    if positions_df.empty:
        positions = pd.DataFrame(columns=POSITION_COLUMNS)
    else:
        positions = positions_df.copy()
        for col in POSITION_COLUMNS:
            if col not in positions.columns:
                positions[col] = np.nan
        if "time" in positions.columns:
            positions["time"] = positions["time"].map(_unix_to_timestamp)
        positions = positions[POSITION_COLUMNS]

    spec_columns = [
        "symbol", "description", "path", "selected", "visible", "trade_mode", "can_open",
        "contract_size", "tick_size", "tick_value", "tick_value_profit", "tick_value_loss", "point", "digits",
        "volume_min", "volume_max", "volume_step", "currency_base",
        "currency_profit", "currency_margin", "swap_long", "swap_short",
    ]
    if not symbols_df.empty:
        specs = symbols_df.copy()
        for col in spec_columns:
            if col not in specs.columns:
                specs[col] = np.nan
        specs = specs[[c for c in [
            "symbol", "description", "path", "selected", "visible", "trade_mode", "can_open",
            "bid", "ask", "last", "contract_size", "tick_size",
            "tick_value", "tick_value_profit", "tick_value_loss", "point", "digits",
            "volume_min", "volume_max", "volume_step", "currency_base",
            "currency_profit", "currency_margin", "swap_long", "swap_short",
        ] if c in specs.columns]].drop_duplicates(subset=["symbol"]).reset_index(drop=True)
    else:
        if not positions.empty:
            fallback_cols = [c for c in spec_columns if c in positions.columns]
            specs = positions[fallback_cols].drop_duplicates(subset=["symbol"]).reset_index(drop=True)
            for col in spec_columns:
                if col not in specs.columns:
                    specs[col] = np.nan
            specs = specs[spec_columns]
        else:
            specs = pd.DataFrame(columns=spec_columns)

    # Overlay the fast watched-symbol quotes (2s bridge timer) on top of the
    # slower 60s broker catalog. This keeps Prop Desk marks current without
    # exporting the entire broker universe every timer tick.
    try:
        fast_quotes = read_bridge_quotes(config)
    except Exception:
        fast_quotes = pd.DataFrame()
    if not fast_quotes.empty and not specs.empty and "symbol" in specs.columns:
        specs = specs.copy()
        spec_index = {str(v).upper(): idx for idx, v in specs["symbol"].items()}
        for _, q in fast_quotes.iterrows():
            idx = spec_index.get(str(q.get("symbol", "")).upper())
            if idx is None:
                continue
            for col in ("bid", "ask", "last"):
                val = q.get(col)
                if val is not None and not pd.isna(val):
                    specs.at[idx, col] = val
            specs.at[idx, "quote_time_utc"] = q.get("exported_at_utc")

    warnings: list[str] = []
    if config.login and account.get("login") and int(config.login) != int(account["login"]):
        warnings.append("Bridge-Kontonummer weicht von der in secrets.toml konfigurierten Nummer ab.")
    if config.server and account.get("server") and config.server != account["server"]:
        warnings.append("Bridge-Server weicht von secrets.toml ab.")

    return {
        "source": "MT5 LOCAL BRIDGE · READ ONLY",
        "captured_at": captured_at,
        "market_time": market_time,
        "account": account,
        "positions": positions,
        "symbol_specs": specs,
        "symbol_catalog": specs.copy(),
        "terminal_version": None,
        "bridge_directory": str(directory),
        "warnings": warnings,
    }


def get_mt5_snapshot(config: MT5Config) -> dict[str, Any]:
    """Read the current MT5 state without exposing any trading operation."""
    if config.mode == "python":
        return direct_snapshot(config)
    if config.mode == "bridge":
        return bridge_snapshot(config)

    direct_error: Exception | None = None
    if config.has_credentials and mt5_python_available():
        try:
            return direct_snapshot(config)
        except Exception as exc:
            direct_error = exc

    try:
        snap = bridge_snapshot(config)
        if direct_error is not None:
            snap.setdefault("warnings", []).append(
                "Direkte MT5-Python-Verbindung fehlgeschlagen; lokale Bridge wurde verwendet."
            )
        return snap
    except MT5BridgeError as bridge_error:
        if direct_error is not None:
            raise MT5ConnectionError(
                f"Direkte MT5-Verbindung fehlgeschlagen ({direct_error}). "
                f"Bridge ebenfalls nicht verfügbar ({bridge_error})."
            ) from direct_error
        if config.has_credentials and not mt5_python_available():
            raise MT5UnavailableError(
                "MetaTrader5-Pythonmodul ist in dieser Umgebung nicht verfügbar und "
                "es wurde keine lokale MT5-Bridge gefunden."
            ) from bridge_error
        raise


QUOTE_WATCH_FILE = "cot_mt5_quote_watch.csv"
QUOTES_FILE = "cot_mt5_quotes.csv"


def write_bridge_quote_watch(config: MT5Config, symbols: list[str] | tuple[str, ...] | set[str]) -> Path:
    """Publish the minimal symbol watch-list consumed by the local read-only EA."""
    directory = discover_bridge_directory(config.bridge_common_path)
    if directory is None:
        raise MT5BridgeError("Keine MT5-Bridge-Dateien gefunden; Quote-Watch kann nicht geschrieben werden.")
    clean = sorted({str(symbol or "").strip() for symbol in symbols if str(symbol or "").strip()})
    path = directory / QUOTE_WATCH_FILE
    tmp = directory / (QUOTE_WATCH_FILE + ".tmp")
    payload = "symbol\n" + "".join(f"{symbol}\n" for symbol in clean)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    return path


def read_bridge_quotes(config: MT5Config, *, max_age_seconds: int | None = None) -> pd.DataFrame:
    """Read the fast watched-symbol quote export produced every bridge timer tick."""
    directory = discover_bridge_directory(config.bridge_common_path)
    if directory is None:
        raise MT5BridgeError("Keine MT5-Bridge-Dateien gefunden; Live-Quotes sind nicht verfügbar.")
    path = directory / QUOTES_FILE
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "bid", "ask", "last", "exported_at_utc", "tick_age_seconds", "trade_mode", "can_open"])
    age_limit = int(max_age_seconds or config.bridge_max_age_seconds)
    file_age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    if file_age > age_limit:
        return pd.DataFrame(columns=["symbol", "bid", "ask", "last", "exported_at_utc", "tick_age_seconds", "trade_mode", "can_open"])
    df = _read_bridge_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "bid", "ask", "last", "exported_at_utc", "tick_age_seconds", "trade_mode", "can_open"])
    out = df.copy()
    for col in ("bid", "ask", "last"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "exported_at_utc_unix" in out.columns:
        out["exported_at_utc"] = pd.to_datetime(pd.to_numeric(out["exported_at_utc_unix"], errors="coerce"), unit="s", utc=True, errors="coerce")
    else:
        out["exported_at_utc"] = pd.Timestamp.fromtimestamp(path.stat().st_mtime, tz="UTC")
    if "tick_age_seconds" in out.columns:
        out["tick_age_seconds"] = pd.to_numeric(out["tick_age_seconds"], errors="coerce")
    else:
        # Older bridge versions do not provide a timezone-safe tick age. They are
        # intentionally not eligible for live execution; history sync remains the safety net.
        out["tick_age_seconds"] = pd.NA
    for col in ("trade_mode", "can_open"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
