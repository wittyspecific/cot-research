from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .ftmo_risk import classify_cluster


TRUE_VALUES = {"1", "true", "yes", "ja", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "nein", "n", "off", ""}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    text = str(value).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    try:
        return bool(int(float(text)))
    except (TypeError, ValueError):
        return default


def normalize_symbol_catalog(catalog: pd.DataFrame | None) -> pd.DataFrame:
    """Normalize the MT5 broker symbol catalog for reuse across UI modules.

    V3.6.0.1 uses the complete broker-side catalog exported by the bridge, not
    only Market Watch. Older bridge files remain readable: if `can_open` is not
    present, symbols are kept unless they are obviously unusable.
    """
    if catalog is None or not isinstance(catalog, pd.DataFrame) or catalog.empty:
        return pd.DataFrame()
    if "symbol" not in catalog.columns:
        return pd.DataFrame()

    out = catalog.copy()
    out["symbol"] = out["symbol"].astype(str).str.strip()
    out = out[out["symbol"] != ""].drop_duplicates(subset=["symbol"], keep="first")

    for col in ("selected", "visible", "can_open"):
        if col in out.columns:
            out[col] = out[col].map(_as_bool)

    if "can_open" not in out.columns:
        # Legacy catalog fallback. A symbol with valid volume/tick metadata is
        # useful for planning even if the old bridge did not export trade mode.
        vol = pd.to_numeric(out.get("volume_min", np.nan), errors="coerce")
        tick = pd.to_numeric(out.get("tick_size", np.nan), errors="coerce")
        out["can_open"] = (vol.fillna(0) > 0) & (tick.fillna(0) > 0)
        if not bool(out["can_open"].any()):
            out["can_open"] = True

    if "description" not in out.columns:
        out["description"] = ""
    if "path" not in out.columns:
        out["path"] = ""

    out["description"] = out["description"].fillna("").astype(str).str.strip()
    out["path"] = out["path"].fillna("").astype(str).str.strip()
    out["cluster"] = out.apply(
        lambda r: classify_cluster(
            str(r.get("symbol", "")),
            str(r.get("currency_base", "") or ""),
            str(r.get("currency_profit", "") or ""),
        ),
        axis=1,
    )
    return out.reset_index(drop=True)


def openable_symbol_catalog(catalog: pd.DataFrame | None) -> pd.DataFrame:
    """Return symbols that can be used for a new trade plan/risk calculation."""
    out = normalize_symbol_catalog(catalog)
    if out.empty:
        return out
    openable = out[out["can_open"]].copy()
    # Defensive fallback for legacy/broker-specific catalogs.
    return openable.reset_index(drop=True) if not openable.empty else out.reset_index(drop=True)


def symbol_display_label(row: dict[str, Any] | pd.Series) -> str:
    symbol = str(row.get("symbol", "") or "")
    desc = str(row.get("description", "") or "").strip()
    cluster = str(row.get("cluster", "") or "").strip()
    market_watch = _as_bool(row.get("selected", False))

    parts = [symbol]
    if desc and desc.upper() != symbol.upper():
        parts.append(desc)
    if cluster:
        parts.append(cluster)
    if market_watch:
        parts.append("Market Watch")
    return " · ".join(parts)


def symbol_label_map(catalog: pd.DataFrame | None) -> dict[str, str]:
    out = openable_symbol_catalog(catalog)
    if out.empty:
        return {}
    return {
        str(row["symbol"]): symbol_display_label(row)
        for _, row in out.iterrows()
    }
