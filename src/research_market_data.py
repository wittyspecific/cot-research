from __future__ import annotations

from io import StringIO
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


def load_fred_series(series_id: str, *, timeout: int = 20) -> pd.Series:
    series_id = str(series_id or "").strip()
    if not series_id:
        return pd.Series(dtype=float)
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series_id
    request = Request(url, headers={"User-Agent": "Quant-Research/3.22", "Accept": "text/csv,*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        frame = pd.read_csv(StringIO(raw))
    except Exception:
        return pd.Series(dtype=float)
    if frame.empty or len(frame.columns) < 2:
        return pd.Series(dtype=float)
    date_col = frame.columns[0]
    value_col = series_id if series_id in frame.columns else frame.columns[1]
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    values = pd.to_numeric(frame[value_col], errors="coerce")
    out = pd.Series(values.to_numpy(), index=dates, name=series_id, dtype=float)
    out = out.loc[out.index.notna()].dropna()
    return out.sort_index()


def percentile_rank(history: pd.Series, value: float | None = None) -> float:
    series = pd.to_numeric(pd.Series(history), errors="coerce").dropna()
    if series.empty:
        return np.nan
    x = float(series.iloc[-1]) if value is None else float(value)
    return float((series <= x).mean() * 100.0)


def last_change(series: pd.Series, periods: int) -> float:
    clean = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    if len(clean) <= int(periods):
        return np.nan
    return float(clean.iloc[-1] - clean.iloc[-1 - int(periods)])


def last_pct_change(series: pd.Series, periods: int) -> float:
    clean = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    if len(clean) <= int(periods):
        return np.nan
    old = float(clean.iloc[-1 - int(periods)])
    new = float(clean.iloc[-1])
    if not np.isfinite(old) or old == 0:
        return np.nan
    return float(new / old - 1.0)
