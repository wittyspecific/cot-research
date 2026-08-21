from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
import re
from typing import Iterable
from urllib.request import Request, urlopen
import zipfile

import pandas as pd


@dataclass
class YieldSeriesResult:
    currency: str
    label: str
    source: str
    source_url: str
    series: pd.Series
    status: str = "OK"
    note: str = ""

    @property
    def as_of(self):
        if self.series is None or self.series.empty:
            return None
        return pd.Timestamp(self.series.index.max())


USD_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2"
EUR_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBSSY/"
    "D.REN.EUR.A610.000000WT0202.A?format=csv&lang=en"
)
CAD_URL = "https://www.bankofcanada.ca/valet/observations/V39051/json"
AUD_URL = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
NZD_URL = (
    "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/"
    "series/b/b2/hb2-daily-close.xlsx"
)
JPY_URL = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/"
    "interest_rate/historical/jgbcme_all.csv"
)
GBP_URL = (
    "https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
    "yield-curves/latest-yield-curve-data.zip"
)


def _http_get_bytes(url: str, timeout: int = 20) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "COT-Research-Yield-Spreads/3.16",
            "Accept": "*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _clean_series(
    dates: Iterable,
    values: Iterable,
    *,
    name: str,
) -> pd.Series:
    frame = pd.DataFrame({"date": list(dates), "value": list(values)})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["date", "value"])
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    series = frame.set_index("date")["value"].astype(float)
    series.name = name
    return series


def _series_from_table_scan(
    frame: pd.DataFrame,
    *,
    name: str,
    target_patterns: tuple[str, ...],
) -> pd.Series:
    """Extract a date/value series from messy official CSV/XLSX tables.

    Searches the first rows for a column whose header-like cell contains
    a 2-year target phrase, then finds a date-like column automatically.
    """
    if frame is None or frame.empty:
        return pd.Series(dtype=float, name=name)

    work = frame.copy()
    work = work.reset_index(drop=True)
    max_header_rows = min(len(work), 40)

    value_col = None
    header_row = None
    for r in range(max_header_rows):
        for c in range(work.shape[1]):
            cell = str(work.iat[r, c] if pd.notna(work.iat[r, c]) else "")
            normalized = re.sub(r"\s+", " ", cell.strip().lower())
            if any(re.search(pattern, normalized) for pattern in target_patterns):
                value_col = c
                header_row = r
                break
        if value_col is not None:
            break

    if value_col is None:
        return pd.Series(dtype=float, name=name)

    candidate_rows = work.iloc[(header_row + 1 if header_row is not None else 0):].copy()
    if candidate_rows.empty:
        return pd.Series(dtype=float, name=name)

    best_date_col = None
    best_valid = 0
    for c in range(candidate_rows.shape[1]):
        parsed = pd.to_datetime(candidate_rows.iloc[:, c], errors="coerce")
        valid = int(parsed.notna().sum())
        if valid > best_valid:
            best_valid = valid
            best_date_col = c

    if best_date_col is None or best_valid < 3:
        return pd.Series(dtype=float, name=name)

    return _clean_series(
        candidate_rows.iloc[:, best_date_col],
        candidate_rows.iloc[:, value_col],
        name=name,
    )


def _series_from_csv_bytes(
    raw: bytes,
    *,
    name: str,
    target_patterns: tuple[str, ...],
) -> pd.Series:
    text = raw.decode("utf-8-sig", errors="replace")
    attempts = []
    for sep in (",", ";", "\t"):
        try:
            attempts.append(pd.read_csv(StringIO(text), sep=sep, header=None))
        except Exception:
            pass
    for frame in attempts:
        series = _series_from_table_scan(
            frame,
            name=name,
            target_patterns=target_patterns,
        )
        if not series.empty:
            return series
    return pd.Series(dtype=float, name=name)


def fetch_usd_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(USD_URL)
    frame = pd.read_csv(BytesIO(raw))
    date_col = "DATE" if "DATE" in frame.columns else frame.columns[0]
    value_col = "DGS2" if "DGS2" in frame.columns else frame.columns[-1]
    series = _clean_series(frame[date_col], frame[value_col], name="USD")
    return YieldSeriesResult(
        "USD",
        "US Treasury 2Y",
        "Federal Reserve / FRED",
        USD_URL,
        series,
    )


def fetch_eur_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(EUR_URL)
    text = raw.decode("utf-8-sig", errors="replace")

    # Bundesbank CSV is semicolon-delimited and may contain metadata rows.
    frame = pd.read_csv(StringIO(text), sep=";", header=None)
    series = _series_from_table_scan(
        frame,
        name="EUR",
        target_patterns=(
            r"2[\s\-]?year",
            r"two[\s\-]?year",
            r"0202",
            r"2,0 jahr",
        ),
    )

    # Some Bundesbank responses expose TIME_PERIOD / OBS_VALUE as a normal table.
    if series.empty:
        for skip in range(0, min(15, len(text.splitlines()))):
            try:
                candidate = pd.read_csv(StringIO(text), sep=";", skiprows=skip)
            except Exception:
                continue
            lowered = {str(c).strip().upper(): c for c in candidate.columns}
            if "TIME_PERIOD" in lowered and "OBS_VALUE" in lowered:
                series = _clean_series(
                    candidate[lowered["TIME_PERIOD"]],
                    candidate[lowered["OBS_VALUE"]],
                    name="EUR",
                )
                break

    if series.empty:
        raise ValueError("Bundesbank 2Y series could not be parsed.")

    return YieldSeriesResult(
        "EUR",
        "German 2Y Schatz",
        "Deutsche Bundesbank",
        EUR_URL,
        series,
    )


def fetch_cad_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(CAD_URL)
    payload = json.loads(raw.decode("utf-8"))
    observations = payload.get("observations", [])
    dates, values = [], []
    for item in observations:
        dates.append(item.get("d"))
        node = item.get("V39051") or {}
        values.append(node.get("v"))
    series = _clean_series(dates, values, name="CAD")
    return YieldSeriesResult(
        "CAD",
        "Canada Government 2Y",
        "Bank of Canada",
        CAD_URL,
        series,
    )


def fetch_jpy_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(JPY_URL)
    text = raw.decode("utf-8-sig", errors="replace")
    frame = pd.read_csv(StringIO(text))

    date_col = frame.columns[0]
    value_col = None
    for column in frame.columns:
        normalized = str(column).strip().lower()
        if normalized in {"2y", "2-year", "2 year", "2 years"} or re.search(
            r"(^|\D)2[\s\-]?year", normalized
        ):
            value_col = column
            break

    if value_col is None:
        series = _series_from_csv_bytes(
            raw,
            name="JPY",
            target_patterns=(r"2[\s\-]?year", r"\b2y\b", r"2 years"),
        )
    else:
        series = _clean_series(frame[date_col], frame[value_col], name="JPY")

    if series.empty:
        raise ValueError("Japan MOF 2Y series could not be parsed.")

    return YieldSeriesResult(
        "JPY",
        "Japan Government Bond 2Y",
        "Japan Ministry of Finance",
        JPY_URL,
        series,
    )


def fetch_aud_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(AUD_URL)
    series = _series_from_csv_bytes(
        raw,
        name="AUD",
        target_patterns=(
            r"australian government.*2[\s\-]?year",
            r"2[\s\-]?year.*australian government",
            r"2[\s\-]?year bond",
        ),
    )
    if series.empty:
        raise ValueError("RBA F2 2Y series could not be parsed.")
    return YieldSeriesResult(
        "AUD",
        "Australian Government 2Y",
        "Reserve Bank of Australia",
        AUD_URL,
        series,
        note="RBA F2 contains daily observations but is normally published weekly with a short lag.",
    )


def _read_excel_sheets(raw: bytes) -> list[pd.DataFrame]:
    book = pd.ExcelFile(BytesIO(raw))
    frames = []
    for sheet in book.sheet_names:
        try:
            frame = pd.read_excel(book, sheet_name=sheet, header=None)
            frame.attrs["sheet_name"] = sheet
            frames.append(frame)
        except Exception:
            continue
    return frames


def fetch_nzd_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(NZD_URL)
    series = pd.Series(dtype=float, name="NZD")
    for frame in _read_excel_sheets(raw):
        series = _series_from_table_scan(
            frame,
            name="NZD",
            target_patterns=(
                r"2[\s\-]?year",
                r"2 year government",
                r"government bond.*2",
            ),
        )
        if not series.empty:
            break
    if series.empty:
        raise ValueError("RBNZ B2 2Y series could not be parsed.")
    return YieldSeriesResult(
        "NZD",
        "New Zealand Government 2Y",
        "Reserve Bank of New Zealand",
        NZD_URL,
        series,
        note="RBNZ B2 is daily closing data, normally published with a one-business-day lag.",
    )


def fetch_gbp_2y() -> YieldSeriesResult:
    raw = _http_get_bytes(GBP_URL)
    series = pd.Series(dtype=float, name="GBP")

    with zipfile.ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()

        # Prefer files that look like current nominal government/spot curve data.
        preferred = sorted(
            names,
            key=lambda n: (
                "nominal" not in n.lower(),
                "spot" not in n.lower(),
                "government" not in n.lower() and "glc" not in n.lower(),
            ),
        )

        for member in preferred:
            lower = member.lower()
            try:
                member_raw = archive.read(member)
            except Exception:
                continue

            frames = []
            if lower.endswith((".xlsx", ".xls")):
                try:
                    frames = _read_excel_sheets(member_raw)
                except Exception:
                    continue
            elif lower.endswith(".csv"):
                try:
                    text = member_raw.decode("utf-8-sig", errors="replace")
                    frames = [pd.read_csv(StringIO(text), header=None)]
                except Exception:
                    continue
            else:
                continue

            for frame in frames:
                sheet_name = str(frame.attrs.get("sheet_name", "")).lower()
                contextual_name = f"{lower} {sheet_name}"
                if "forward" in contextual_name and "spot" not in contextual_name:
                    continue
                candidate = _series_from_table_scan(
                    frame,
                    name="GBP",
                    target_patterns=(
                        r"^2\.?0?\s*$",
                        r"2[\s\-]?year",
                        r"2 years",
                    ),
                )
                if not candidate.empty:
                    series = candidate
                    break
            if not series.empty:
                break

    if series.empty:
        raise ValueError("Bank of England 2Y nominal spot series could not be parsed.")

    return YieldSeriesResult(
        "GBP",
        "UK 2Y nominal government spot yield",
        "Bank of England",
        GBP_URL,
        series,
        note="Official fitted nominal government yield curve; typically published next business day.",
    )


FETCHERS = {
    "USD": fetch_usd_2y,
    "EUR": fetch_eur_2y,
    "GBP": fetch_gbp_2y,
    "JPY": fetch_jpy_2y,
    "CAD": fetch_cad_2y,
    "AUD": fetch_aud_2y,
    "NZD": fetch_nzd_2y,
}


UNAVAILABLE = {
    "CHF": (
        "Swiss 2Y",
        "SNB public data",
        "The SNB publishes 2Y Confederation yields, but the public current-series "
        "automation/freshness is not yet reliable enough for this production adapter. "
        "No stale value is used.",
    ),
    "MXN": (
        "Mexico 2Y",
        "Banco de México",
        "Banxico has 2Y CETES/Mexican rates data, but a stable authenticated SIE API "
        "adapter is not configured yet. No web scraping is used.",
    ),
}


def fetch_yield_universe() -> dict[str, YieldSeriesResult]:
    results: dict[str, YieldSeriesResult] = {}

    for currency, fetcher in FETCHERS.items():
        try:
            item = fetcher()
            if item.series.empty:
                item.status = "N/V"
                item.note = (item.note + " Empty series.").strip()
            results[currency] = item
        except Exception as exc:
            results[currency] = YieldSeriesResult(
                currency=currency,
                label=f"{currency} 2Y",
                source="Official source",
                source_url="",
                series=pd.Series(dtype=float, name=currency),
                status="ERROR",
                note=f"{type(exc).__name__}: {exc}",
            )

    for currency, (label, source, note) in UNAVAILABLE.items():
        results[currency] = YieldSeriesResult(
            currency=currency,
            label=label,
            source=source,
            source_url="",
            series=pd.Series(dtype=float, name=currency),
            status="N/V",
            note=note,
        )

    return results


def data_age_days(result: YieldSeriesResult, now=None) -> int | None:
    if result.as_of is None:
        return None
    if now is None:
        now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    else:
        now = pd.Timestamp(now)
        if now.tzinfo is not None:
            now = now.tz_convert("UTC").tz_localize(None)
    as_of = pd.Timestamp(result.as_of)
    if as_of.tzinfo is not None:
        as_of = as_of.tz_convert("UTC").tz_localize(None)
    return max(0, int((now.normalize() - as_of.normalize()).days))


def freshness_status(result: YieldSeriesResult, now=None) -> str:
    age = data_age_days(result, now=now)
    if age is None:
        return "N/V"
    if age <= 4:
        return "FRESH"
    if age <= 10:
        return "LAGGED"
    return "STALE"


def parse_pair(pair: str) -> tuple[str, str]:
    text = re.sub(r"[^A-Za-z]", "", str(pair)).upper()
    if len(text) != 6:
        raise ValueError(f"Ungültiges FX-Paar: {pair}")
    return text[:3], text[3:]


def spread_series(
    base: pd.Series,
    quote: pd.Series,
    *,
    name: str = "spread",
) -> pd.Series:
    frame = pd.concat(
        [base.rename("base"), quote.rename("quote")],
        axis=1,
        join="inner",
    ).dropna()
    if frame.empty:
        return pd.Series(dtype=float, name=name)
    out = (frame["base"] - frame["quote"]).astype(float)
    out.name = name
    return out


def _obs_delta_bp(series: pd.Series, periods: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= periods:
        return None
    return float((clean.iloc[-1] - clean.iloc[-(periods + 1)]) * 100.0)


def pair_spread_snapshot(
    pair: str,
    universe: dict[str, YieldSeriesResult],
) -> dict:
    base_ccy, quote_ccy = parse_pair(pair)
    base_result = universe.get(base_ccy)
    quote_result = universe.get(quote_ccy)

    base_series = (
        base_result.series
        if base_result is not None
        else pd.Series(dtype=float)
    )
    quote_series = (
        quote_result.series
        if quote_result is not None
        else pd.Series(dtype=float)
    )

    spread = spread_series(base_series, quote_series, name=pair)

    row = {
        "pair": pair.upper(),
        "base": base_ccy,
        "quote": quote_ccy,
        "available": not spread.empty,
        "spread_bp": None,
        "delta_5d_bp": None,
        "delta_20d_bp": None,
        "delta_60d_bp": None,
        "direction_20d": "N/V",
        "as_of": None,
    }

    if spread.empty:
        return row

    current = float(spread.iloc[-1] * 100.0)
    d5 = _obs_delta_bp(spread, 5)
    d20 = _obs_delta_bp(spread, 20)
    d60 = _obs_delta_bp(spread, 60)

    if d20 is None:
        direction = "N/V"
    elif d20 > 0:
        direction = f"{base_ccy} +"
    elif d20 < 0:
        direction = f"{quote_ccy} +"
    else:
        direction = "NEUTRAL"

    return {
        **row,
        "available": True,
        "spread_bp": current,
        "delta_5d_bp": d5,
        "delta_20d_bp": d20,
        "delta_60d_bp": d60,
        "direction_20d": direction,
        "as_of": pd.Timestamp(spread.index[-1]),
    }


DEFAULT_PAIRS = (
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "USDMXN",
    "EURJPY",
    "GBPJPY",
    "AUDJPY",
    "CADJPY",
    "EURGBP",
    "EURCHF",
    "GBPCHF",
    "AUDCAD",
    "AUDNZD",
    "NZDCAD",
    "CADCHF",
    "AUDCHF",
    "NZDJPY",
)


def pair_table(
    universe: dict[str, YieldSeriesResult],
    pairs: Iterable[str] = DEFAULT_PAIRS,
) -> pd.DataFrame:
    return pd.DataFrame(
        [pair_spread_snapshot(pair, universe) for pair in pairs]
    )
# V3.16.1 · HISTORICAL NORMALIZATION
NORMALIZATION_LOOKBACK_YEARS = 5
NORMALIZATION_MIN_HISTORY = 252


def percentile_strength(percentile: float | None) -> str:
    if percentile is None or pd.isna(percentile):
        return "N/V"
    value = float(percentile)
    if value >= 90.0:
        return "EXTREME"
    if value >= 75.0:
        return "STRONG"
    if value >= 60.0:
        return "MILD"
    return "NORMAL"


def historical_move_stats(
    spread: pd.Series,
    periods: int,
    *,
    lookback_years: int = NORMALIZATION_LOOKBACK_YEARS,
    min_history: int = NORMALIZATION_MIN_HISTORY,
) -> dict:
    """Normalize the current spread move against its own prior history.

    The current move is excluded from the reference sample. Magnitude uses the
    absolute move, while direction remains a separate sign-based concept.
    """
    clean = spread.dropna().sort_index()
    if len(clean) <= int(periods):
        return {
            "percentile": None,
            "strength": "N/V",
            "history_count": 0,
            "current_move_bp": None,
        }

    moves = (clean.diff(int(periods)) * 100.0).dropna()
    if moves.empty:
        return {
            "percentile": None,
            "strength": "N/V",
            "history_count": 0,
            "current_move_bp": None,
        }

    current_date = pd.Timestamp(moves.index[-1])
    current_move = float(moves.iloc[-1])

    history = moves.iloc[:-1]
    cutoff = current_date - pd.DateOffset(years=int(lookback_years))
    recent = history.loc[history.index >= cutoff]

    # Prefer the 5Y regime window. If an official source has a shorter recent
    # segment but enough older observations, use the full prior history rather
    # than manufacturing a percentile from an undersized sample.
    if len(recent) >= int(min_history):
        sample = recent
    elif len(history) >= int(min_history):
        sample = history
    else:
        return {
            "percentile": None,
            "strength": "N/V",
            "history_count": int(len(recent)),
            "current_move_bp": current_move,
        }

    hist_abs = sample.abs()
    current_abs = abs(current_move)

    less = int((hist_abs < current_abs).sum())
    equal = int((hist_abs == current_abs).sum())

    # Mid-rank empirical percentile handles ties without artificially pushing
    # repeated moves to 100%.
    percentile = 100.0 * (less + 0.5 * equal) / float(len(hist_abs))
    percentile = max(0.0, min(100.0, float(percentile)))

    return {
        "percentile": percentile,
        "strength": percentile_strength(percentile),
        "history_count": int(len(hist_abs)),
        "current_move_bp": current_move,
    }


def _relative_direction(
    delta_bp: float | None,
    base_ccy: str,
    quote_ccy: str,
) -> str:
    if delta_bp is None or pd.isna(delta_bp):
        return "N/V"
    if float(delta_bp) > 0:
        return base_ccy
    if float(delta_bp) < 0:
        return quote_ccy
    return "NEUTRAL"


def _rates_consistency(
    deltas: tuple[float | None, float | None, float | None],
    base_ccy: str,
    quote_ccy: str,
) -> str:
    directions = [
        _relative_direction(value, base_ccy, quote_ccy)
        for value in deltas
    ]
    directions = [d for d in directions if d not in {"N/V", "NEUTRAL"}]

    if not directions:
        return "N/V"

    base_count = directions.count(base_ccy)
    quote_count = directions.count(quote_ccy)
    available = len(directions)

    if base_count == available:
        return f"{available}/{available} {base_ccy}"
    if quote_count == available:
        return f"{available}/{available} {quote_ccy}"

    if base_count > quote_count:
        return f"{base_count}/{available} {base_ccy}"
    if quote_count > base_count:
        return f"{quote_count}/{available} {quote_ccy}"
    return "MIXED"


def pair_spread_snapshot(
    pair: str,
    universe: dict[str, YieldSeriesResult],
) -> dict:
    """V3.16.1: raw spread + 5Y historical normalization."""
    base_ccy, quote_ccy = parse_pair(pair)
    base_result = universe.get(base_ccy)
    quote_result = universe.get(quote_ccy)

    base_series = (
        base_result.series
        if base_result is not None
        else pd.Series(dtype=float)
    )
    quote_series = (
        quote_result.series
        if quote_result is not None
        else pd.Series(dtype=float)
    )

    spread = spread_series(base_series, quote_series, name=pair)

    empty_row = {
        "pair": pair.upper(),
        "base": base_ccy,
        "quote": quote_ccy,
        "available": False,
        "spread_bp": None,
        "delta_5d_bp": None,
        "delta_20d_bp": None,
        "delta_60d_bp": None,
        "percentile_5d": None,
        "percentile_20d": None,
        "percentile_60d": None,
        "strength_5d": "N/V",
        "strength_20d": "N/V",
        "strength_60d": "N/V",
        "normalization_obs_5d": 0,
        "normalization_obs_20d": 0,
        "normalization_obs_60d": 0,
        "direction_20d": "N/V",
        "rates_consistency": "N/V",
        "as_of": None,
    }

    if spread.empty:
        return empty_row

    current = float(spread.iloc[-1] * 100.0)
    d5 = _obs_delta_bp(spread, 5)
    d20 = _obs_delta_bp(spread, 20)
    d60 = _obs_delta_bp(spread, 60)

    stats5 = historical_move_stats(spread, 5)
    stats20 = historical_move_stats(spread, 20)
    stats60 = historical_move_stats(spread, 60)

    if d20 is None:
        direction = "N/V"
    elif d20 > 0:
        direction = f"{base_ccy} +"
    elif d20 < 0:
        direction = f"{quote_ccy} +"
    else:
        direction = "NEUTRAL"

    return {
        **empty_row,
        "available": True,
        "spread_bp": current,
        "delta_5d_bp": d5,
        "delta_20d_bp": d20,
        "delta_60d_bp": d60,
        "percentile_5d": stats5["percentile"],
        "percentile_20d": stats20["percentile"],
        "percentile_60d": stats60["percentile"],
        "strength_5d": stats5["strength"],
        "strength_20d": stats20["strength"],
        "strength_60d": stats60["strength"],
        "normalization_obs_5d": stats5["history_count"],
        "normalization_obs_20d": stats20["history_count"],
        "normalization_obs_60d": stats60["history_count"],
        "direction_20d": direction,
        "rates_consistency": _rates_consistency(
            (d5, d20, d60),
            base_ccy,
            quote_ccy,
        ),
        "as_of": pd.Timestamp(spread.index[-1]),
    }

# V3.16.2 · YIELD DATA ADAPTER REPAIR
from urllib.error import HTTPError, URLError


EUR_URL_V3162 = (
    "https://api.statistiken.bundesbank.de/rest/data/BBSSY/"
    "D.REN.EUR.A610.000000WT0202.A?format=csv&lang=en"
)
CAD_URL_V3162 = (
    "https://www.bankofcanada.ca/valet/observations/"
    "V39051/json?start_date=2010-01-01"
)
AUD_URL_V3162 = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
NZD_URL_V3162 = (
    "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/"
    "series/b/b2/hb2-daily-close.xlsx"
)
JPY_HISTORY_URL_V3162 = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/"
    "interest_rate/historical/jgbcme_all.csv"
)
JPY_CURRENT_URL_V3162 = (
    "https://www.mof.go.jp/english/policy/jgbs/reference/"
    "interest_rate/jgbcme.csv"
)
GBP_LATEST_URL_V3162 = (
    "https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
    "yield-curves/latest-yield-curve-data.zip"
)
GBP_ARCHIVE_URL_V3162 = (
    "https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
    "yield-curves/glcnominalddata.zip"
)


def _real_date_series(values) -> pd.Series:
    raw = pd.Series(values)

    if pd.api.types.is_datetime64_any_dtype(raw):
        parsed = pd.to_datetime(raw, errors="coerce")
    else:
        text = raw.astype(str).str.strip()
        date_like = text.str.match(
            r"^(?:"
            r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
            r"|"
            r"\d{1,2}[-/.]\d{1,2}[-/.]\d{4}"
            r"|"
            r"\d{1,2}-[A-Za-z]{3}-\d{4}"
            r")(?:[ T].*)?$",
            na=False,
        )
        parsed = pd.to_datetime(
            text.where(date_like),
            errors="coerce",
            dayfirst=False,
        )

    years = parsed.dt.year
    valid_year = years.between(1970, pd.Timestamp.utcnow().year + 1)
    return parsed.where(valid_year)


def _best_real_date_column(
    frame: pd.DataFrame,
    *,
    start_row: int = 0,
    min_valid: int = 3,
) -> tuple[int | None, pd.Series]:
    work = frame.iloc[int(start_row):].reset_index(drop=True)
    best_col = None
    best_dates = pd.Series(dtype="datetime64[ns]")
    best_count = 0

    for c in range(work.shape[1]):
        dates = _real_date_series(work.iloc[:, c])
        count = int(dates.notna().sum())
        if count > best_count:
            best_col = c
            best_dates = dates
            best_count = count

    if best_col is None or best_count < int(min_valid):
        return None, pd.Series(dtype="datetime64[ns]")
    return int(best_col), best_dates


def _parse_series_specific_csv(raw: bytes, *, name: str) -> pd.Series:
    text = raw.decode("utf-8-sig", errors="replace")
    candidates = []

    for sep in (";", ",", "\t"):
        try:
            frame = pd.read_csv(
                StringIO(text),
                sep=sep,
                header=None,
                dtype=object,
                engine="python",
            )
        except Exception:
            continue
        if frame.shape[1] >= 2:
            candidates.append(frame)

    best = pd.Series(dtype=float, name=name)
    best_count = 0

    for frame in candidates:
        date_col, dates = _best_real_date_column(frame, min_valid=3)
        if date_col is None:
            continue

        for c in range(frame.shape[1]):
            if c == date_col:
                continue
            values = pd.to_numeric(
                frame.iloc[:, c].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            mask = dates.notna() & values.notna()
            count = int(mask.sum())
            if count <= best_count:
                continue

            series = _clean_series(
                dates[mask],
                values[mask],
                name=name,
            )
            if not series.empty:
                best = series
                best_count = count

    return best


def _parse_bundesbank_2y(raw: bytes) -> pd.Series:
    return _parse_series_specific_csv(raw, name="EUR")


def _parse_boc_2y(raw: bytes) -> pd.Series:
    payload = json.loads(raw.decode("utf-8"))
    observations = payload.get("observations") or []
    dates, values = [], []

    for item in observations:
        if not isinstance(item, dict):
            continue
        node = item.get("V39051")
        value = node.get("v") if isinstance(node, dict) else node
        dates.append(item.get("d"))
        values.append(value)

    return _clean_series(dates, values, name="CAD")


def _parse_rba_2y(raw: bytes) -> pd.Series:
    text = raw.decode("utf-8-sig", errors="replace")
    frame = pd.read_csv(
        StringIO(text),
        header=None,
        dtype=object,
        engine="python",
    )

    value_col = None
    series_row = None

    for r in range(min(len(frame), 30)):
        for c in range(frame.shape[1]):
            cell = str(frame.iat[r, c] if pd.notna(frame.iat[r, c]) else "").strip()
            if cell.upper() == "FCMYGBAG2D":
                value_col = int(c)
                series_row = int(r)
                break
        if value_col is not None:
            break

    if value_col is None:
        for r in range(min(len(frame), 30)):
            for c in range(frame.shape[1]):
                cell = re.sub(
                    r"\s+",
                    " ",
                    str(frame.iat[r, c] if pd.notna(frame.iat[r, c]) else "")
                    .strip()
                    .lower(),
                )
                if cell == "australian government 2 year bond":
                    value_col = int(c)
                    series_row = int(r)
                    break
            if value_col is not None:
                break

    if value_col is None:
        raise ValueError("RBA series FCMYGBAG2D not found in F2.")

    start = int(series_row or 0) + 1
    date_col, dates = _best_real_date_column(frame, start_row=start, min_valid=3)
    if date_col is None:
        raise ValueError("RBA F2 real date column not found.")

    work = frame.iloc[start:].reset_index(drop=True)
    values = pd.to_numeric(work.iloc[:, value_col], errors="coerce")
    mask = dates.notna() & values.notna()

    return _clean_series(dates[mask], values[mask], name="AUD")


def _read_excel_candidates(raw: bytes) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    book = pd.ExcelFile(BytesIO(raw))

    for sheet in book.sheet_names:
        try:
            frame = pd.read_excel(
                book,
                sheet_name=sheet,
                header=None,
                dtype=object,
            )
            frame.attrs["sheet_name"] = str(sheet)
            frames.append(frame)
        except Exception:
            continue

    return frames


def _parse_rbnz_2y(raw: bytes) -> pd.Series:
    best = pd.Series(dtype=float, name="NZD")
    best_count = 0

    for frame in _read_excel_candidates(raw):
        value_col = None
        header_row = None

        for r in range(min(len(frame), 40)):
            for c in range(frame.shape[1]):
                cell = re.sub(
                    r"\s+",
                    " ",
                    str(frame.iat[r, c] if pd.notna(frame.iat[r, c]) else "")
                    .strip()
                    .lower(),
                )
                if cell not in {"2 year", "2 yr", "2 years"}:
                    continue

                context_cells = []
                for rr in range(max(0, r - 5), r + 1):
                    for cc in range(max(0, c - 2), min(frame.shape[1], c + 3)):
                        context_cells.append(
                            str(
                                frame.iat[rr, cc]
                                if pd.notna(frame.iat[rr, cc])
                                else ""
                            ).lower()
                        )
                context = " ".join(context_cells)

                if "government" in context or "bond" in context:
                    value_col = int(c)
                    header_row = int(r)
                    break
            if value_col is not None:
                break

        if value_col is None:
            continue

        start = int(header_row or 0) + 1
        date_col, dates = _best_real_date_column(frame, start_row=start, min_valid=3)
        if date_col is None:
            continue

        work = frame.iloc[start:].reset_index(drop=True)
        values = pd.to_numeric(work.iloc[:, value_col], errors="coerce")
        mask = dates.notna() & values.notna()
        candidate = _clean_series(dates[mask], values[mask], name="NZD")

        if len(candidate) > best_count:
            best = candidate
            best_count = len(candidate)

    if best.empty:
        raise ValueError("RBNZ B2 2-year government bond column not found.")
    return best


def _parse_japan_2y(raw: bytes) -> pd.Series:
    text = raw.decode("utf-8-sig", errors="replace")

    for skip in (0, 1, 2):
        try:
            frame = pd.read_csv(StringIO(text), skiprows=skip, dtype=object)
        except Exception:
            continue

        if frame.empty or frame.shape[1] < 2:
            continue

        value_col = None
        for column in frame.columns[1:]:
            label = re.sub(r"\s+", "", str(column).strip().upper())
            if label in {"2Y", "2YEAR", "2YEARS", "2"}:
                value_col = column
                break

        if value_col is None and frame.shape[1] >= 3:
            c1 = re.sub(r"\s+", "", str(frame.columns[1]).strip().upper())
            c2 = re.sub(r"\s+", "", str(frame.columns[2]).strip().upper())
            if c1 in {"1Y", "1", "1YEAR"} and c2 in {"2Y", "2", "2YEAR"}:
                value_col = frame.columns[2]

        if value_col is None:
            continue

        dates = _real_date_series(frame.iloc[:, 0])
        values = pd.to_numeric(frame[value_col], errors="coerce")
        mask = dates.notna() & values.notna()
        series = _clean_series(dates[mask], values[mask], name="JPY")

        if not series.empty:
            return series

    raise ValueError("Japan MOF 2Y column not found.")


def _parse_boe_curve_frame_2y(
    frame: pd.DataFrame,
    *,
    name: str = "GBP",
) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float, name=name)

    value_col = None
    header_row = None

    for r in range(min(len(frame), 50)):
        for c in range(frame.shape[1]):
            raw = frame.iat[r, c]
            numeric = pd.to_numeric(pd.Series([raw]), errors="coerce").iloc[0]

            if pd.notna(numeric) and abs(float(numeric) - 2.0) < 1e-9:
                value_col = int(c)
                header_row = int(r)
                break

            label = re.sub(
                r"\s+",
                "",
                str(raw if pd.notna(raw) else "").strip().lower(),
            )
            if label in {"2y", "2year", "2years", "2.0years"}:
                value_col = int(c)
                header_row = int(r)
                break

        if value_col is not None:
            break

    if value_col is None:
        return pd.Series(dtype=float, name=name)

    start = int(header_row or 0) + 1
    date_col, dates = _best_real_date_column(frame, start_row=start, min_valid=3)
    if date_col is None or int(date_col) == int(value_col):
        return pd.Series(dtype=float, name=name)

    work = frame.iloc[start:].reset_index(drop=True)
    values = pd.to_numeric(work.iloc[:, value_col], errors="coerce")
    mask = dates.notna() & values.notna()

    return _clean_series(dates[mask], values[mask], name=name)


def _parse_boe_zip_2y(raw: bytes) -> pd.Series:
    best = pd.Series(dtype=float, name="GBP")
    best_score = (-1, -1)

    with zipfile.ZipFile(BytesIO(raw)) as archive:
        for member in archive.namelist():
            lower = member.lower()

            if not lower.endswith((".xlsx", ".xls")):
                continue
            if any(token in lower for token in ("real", "inflation", "ois", "blc")):
                continue

            try:
                member_raw = archive.read(member)
                book = pd.ExcelFile(BytesIO(member_raw))
            except Exception:
                continue

            for sheet in book.sheet_names:
                sheet_lower = str(sheet).lower()
                context = f"{lower} {sheet_lower}"

                if "forward" in context and "spot" not in context:
                    continue

                try:
                    frame = pd.read_excel(
                        book,
                        sheet_name=sheet,
                        header=None,
                        dtype=object,
                    )
                except Exception:
                    continue

                candidate = _parse_boe_curve_frame_2y(frame)
                if candidate.empty:
                    continue

                preference = 0
                if "spot" in context:
                    preference += 4
                if "short" in context:
                    preference += 3
                if "nominal" in context or "glc" in context:
                    preference += 2

                score = (preference, len(candidate))
                if score > best_score:
                    best = candidate
                    best_score = score

    if best.empty:
        raise ValueError("BoE nominal spot 2Y series not found in ZIP.")
    return best


def _validate_official_series(
    series: pd.Series,
    *,
    currency: str,
    max_latest_age_days: int = 120,
) -> pd.Series:
    if series is None or series.empty:
        raise ValueError(f"{currency}: empty 2Y series.")

    clean = series.dropna().sort_index()
    clean = clean[~clean.index.duplicated(keep="last")]

    if clean.empty:
        raise ValueError(f"{currency}: no valid observations.")

    latest_date = pd.Timestamp(clean.index[-1])
    if latest_date.tzinfo is not None:
        latest_date = latest_date.tz_convert("UTC").tz_localize(None)

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    age_days = int((now.normalize() - latest_date.normalize()).days)

    if latest_date.year < 2015:
        raise ValueError(
            f"{currency}: impossible latest date {latest_date.date()}."
        )
    if age_days > int(max_latest_age_days):
        raise ValueError(
            f"{currency}: latest official observation is {age_days} days old."
        )

    latest_value = float(clean.iloc[-1])
    if not (-5.0 <= latest_value <= 25.0):
        raise ValueError(
            f"{currency}: implausible 2Y yield {latest_value:.3f}%."
        )

    plausible = clean.between(-5.0, 25.0)
    if float(plausible.mean()) < 0.98:
        raise ValueError(
            f"{currency}: too many implausible yield observations."
        )

    return clean.astype(float)


def fetch_eur_2y_v3162() -> YieldSeriesResult:
    raw = _http_get_bytes(EUR_URL_V3162)
    series = _validate_official_series(
        _parse_bundesbank_2y(raw),
        currency="EUR",
    )
    return YieldSeriesResult(
        "EUR",
        "German 2Y Bundesschatzanweisung",
        "Deutsche Bundesbank",
        EUR_URL_V3162,
        series,
        note=(
            "Official Bundesbank daily yield of the current "
            "two-year Federal Treasury note."
        ),
    )


def fetch_cad_2y_v3162() -> YieldSeriesResult:
    raw = _http_get_bytes(CAD_URL_V3162)
    series = _validate_official_series(
        _parse_boc_2y(raw),
        currency="CAD",
    )
    return YieldSeriesResult(
        "CAD",
        "Canada Government Benchmark 2Y",
        "Bank of Canada",
        CAD_URL_V3162,
        series,
        note="Official Bank of Canada daily benchmark series V39051.",
    )


def fetch_aud_2y_v3162() -> YieldSeriesResult:
    raw = _http_get_bytes(AUD_URL_V3162)
    series = _validate_official_series(
        _parse_rba_2y(raw),
        currency="AUD",
    )
    return YieldSeriesResult(
        "AUD",
        "Australian Government 2Y",
        "Reserve Bank of Australia",
        AUD_URL_V3162,
        series,
        note=(
            "Official RBA F2 series FCMYGBAG2D. Daily observations; "
            "publication can have a short weekly lag."
        ),
    )


def fetch_nzd_2y_v3162() -> YieldSeriesResult:
    raw = _http_get_bytes(NZD_URL_V3162)
    series = _validate_official_series(
        _parse_rbnz_2y(raw),
        currency="NZD",
    )
    return YieldSeriesResult(
        "NZD",
        "New Zealand Government 2Y",
        "Reserve Bank of New Zealand",
        NZD_URL_V3162,
        series,
        note=(
            "Official RBNZ B2 secondary-market 2Y government bond closing yield; "
            "normally published with one-business-day lag."
        ),
    )


def fetch_jpy_2y_v3162() -> YieldSeriesResult:
    historical_raw = _http_get_bytes(JPY_HISTORY_URL_V3162)
    current_raw = _http_get_bytes(JPY_CURRENT_URL_V3162)

    historical = _parse_japan_2y(historical_raw)
    current = _parse_japan_2y(current_raw)

    series = pd.concat([historical, current]).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    series.name = "JPY"
    series = _validate_official_series(series, currency="JPY")

    return YieldSeriesResult(
        "JPY",
        "Japan Government Bond 2Y",
        "Japan Ministry of Finance",
        JPY_CURRENT_URL_V3162,
        series,
        note="Official MOF current + historical JGB yield files merged.",
    )


def fetch_gbp_2y_v3162() -> YieldSeriesResult:
    archive_raw = _http_get_bytes(GBP_ARCHIVE_URL_V3162, timeout=60)
    latest_raw = _http_get_bytes(GBP_LATEST_URL_V3162, timeout=30)

    historical = _parse_boe_zip_2y(archive_raw)
    latest = _parse_boe_zip_2y(latest_raw)

    series = pd.concat([historical, latest]).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    series.name = "GBP"
    series = _validate_official_series(series, currency="GBP")

    return YieldSeriesResult(
        "GBP",
        "UK 2Y nominal government spot yield",
        "Bank of England",
        GBP_LATEST_URL_V3162,
        series,
        note=(
            "Official Bank of England Anderson-Sleath nominal government spot "
            "curve. Daily archive + latest month; exact 2.0Y maturity."
        ),
    )


FETCHERS = {
    "USD": fetch_usd_2y,
    "EUR": fetch_eur_2y_v3162,
    "GBP": fetch_gbp_2y_v3162,
    "JPY": fetch_jpy_2y_v3162,
    "CAD": fetch_cad_2y_v3162,
    "AUD": fetch_aud_2y_v3162,
    "NZD": fetch_nzd_2y_v3162,
}


def fetch_yield_universe() -> dict[str, YieldSeriesResult]:
    results: dict[str, YieldSeriesResult] = {}

    for currency, fetcher in FETCHERS.items():
        try:
            item = fetcher()
            item.series = _validate_official_series(
                item.series,
                currency=currency,
            )
            item.status = "OK"
            results[currency] = item
        except Exception as exc:
            results[currency] = YieldSeriesResult(
                currency=currency,
                label=f"{currency} 2Y",
                source="Official source",
                source_url="",
                series=pd.Series(dtype=float, name=currency),
                status="ERROR",
                note=f"{type(exc).__name__}: {exc}",
            )

    for currency, (label, source, note) in UNAVAILABLE.items():
        results[currency] = YieldSeriesResult(
            currency=currency,
            label=label,
            source=source,
            source_url="",
            series=pd.Series(dtype=float, name=currency),
            status="N/V",
            note=note,
        )

    return results

# V3.16.3 · CAD / AUD / NZD FINAL ADAPTER FIX
import csv
from urllib.parse import urlencode


CAD_LOOKUP_BASE_V3163 = (
    "https://www.bankofcanada.ca/rates/interest-rates/lookup-bond-yields/"
)
RBNZ_B2_URL_V3163 = (
    "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/"
    "series/b/b2/hb2-daily-close.xlsx"
)


def _http_get_bytes_browser(
    url: str,
    timeout: int = 30,
    *,
    referer: str | None = None,
) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
            "text/csv;q=0.8,*/*;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer

    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _parse_cad_lookup_html(raw: bytes) -> pd.Series:
    """Parse the official Bank of Canada lookup result for one selected series."""
    html_text = raw.decode("utf-8", errors="replace")

    try:
        tables = pd.read_html(StringIO(html_text))
    except Exception as exc:
        raise ValueError(f"Bank of Canada HTML tables could not be parsed: {exc}") from exc

    best = pd.Series(dtype=float, name="CAD")
    best_count = 0

    for table in tables:
        if table is None or table.empty or table.shape[1] < 2:
            continue

        work = table.copy()
        work.columns = [str(c) for c in work.columns]

        # Flatten multi-index columns if needed.
        if isinstance(table.columns, pd.MultiIndex):
            work.columns = [
                " ".join(str(part) for part in col if str(part) != "nan").strip()
                for col in table.columns
            ]

        date_col = None
        best_dates = None
        best_dates_count = 0

        for col in work.columns:
            dates = _real_date_series(work[col])
            count = int(dates.notna().sum())
            if count > best_dates_count:
                date_col = col
                best_dates = dates
                best_dates_count = count

        if date_col is None or best_dates_count < 20:
            continue

        preferred_numeric_cols = []
        fallback_numeric_cols = []

        for col in work.columns:
            if col == date_col:
                continue

            label = str(col).lower()
            values = pd.to_numeric(
                work[col].astype(str).str.replace("%", "", regex=False),
                errors="coerce",
            )
            valid = int((best_dates.notna() & values.notna()).sum())

            if valid < 20:
                continue

            if (
                "2 year" in label
                or "2-year" in label
                or "v39051" in label
                or "39051" in label
            ):
                preferred_numeric_cols.append((valid, col, values))
            else:
                fallback_numeric_cols.append((valid, col, values))

        candidates = preferred_numeric_cols or fallback_numeric_cols
        if not candidates:
            continue

        valid, col, values = max(candidates, key=lambda item: item[0])
        mask = best_dates.notna() & values.notna()

        candidate = _clean_series(
            best_dates[mask],
            values[mask],
            name="CAD",
        )

        if len(candidate) > best_count:
            best = candidate
            best_count = len(candidate)

    if best.empty:
        raise ValueError("Bank of Canada V39051 result table not found.")

    return best


def fetch_cad_2y_v3163() -> YieldSeriesResult:
    """Official Bank of Canada V39051 via the bank's own series lookup page."""
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    start = (now - pd.DateOffset(years=6)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    params = {
        "lookupPage": "lookup_bond_yields.php",
        "startRange": start,
        "rangeType": "dates",
        "dFrom": start,
        "dTo": end,
        "rangeValue": "1",
        "rangeWeeklyValue": "1",
        "rangeMonthlyValue": "1",
        "series[]": "LOOKUPS_V39051",
        "submit_button": "Submit",
    }
    url = CAD_LOOKUP_BASE_V3163 + "?" + urlencode(params, doseq=True)

    raw = _http_get_bytes_browser(
        url,
        timeout=30,
        referer=CAD_LOOKUP_BASE_V3163,
    )
    series = _validate_official_series(
        _parse_cad_lookup_html(raw),
        currency="CAD",
    )

    return YieldSeriesResult(
        "CAD",
        "Canada Government Benchmark 2Y",
        "Bank of Canada",
        CAD_LOOKUP_BASE_V3163,
        series,
        note=(
            "Official Bank of Canada daily benchmark bond yield V39051. "
            "Loaded from the Bank's official bond-yield lookup because V39051 "
            "is not exposed by the current Valet route used by V3.16.2."
        ),
    )


def _ragged_csv_frame(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(StringIO(text)))

    if not rows:
        return pd.DataFrame()

    width = max(len(row) for row in rows)
    padded = [
        list(row) + [""] * (width - len(row))
        for row in rows
    ]
    return pd.DataFrame(padded, dtype=object)


def _parse_rba_2y_v3163(raw: bytes) -> pd.Series:
    """Parse RBA F2 without assuming every CSV row has the same width."""
    frame = _ragged_csv_frame(raw)
    if frame.empty:
        raise ValueError("RBA F2 CSV is empty.")

    value_col = None
    series_row = None

    for r in range(min(len(frame), 80)):
        for c in range(frame.shape[1]):
            cell = str(
                frame.iat[r, c]
                if pd.notna(frame.iat[r, c])
                else ""
            ).strip()
            if cell.upper() == "FCMYGBAG2D":
                value_col = int(c)
                series_row = int(r)
                break
        if value_col is not None:
            break

    if value_col is None:
        raise ValueError("RBA exact series FCMYGBAG2D not found.")

    start = int(series_row) + 1
    work = frame.iloc[start:].reset_index(drop=True)

    date_col = None
    dates = pd.Series(dtype="datetime64[ns]")
    best_count = 0

    for c in range(work.shape[1]):
        parsed = _real_date_series(work.iloc[:, c])
        count = int(parsed.notna().sum())
        if count > best_count:
            date_col = int(c)
            dates = parsed
            best_count = count

    if date_col is None or best_count < 20:
        raise ValueError("RBA F2 date column not found.")

    values = pd.to_numeric(
        work.iloc[:, value_col],
        errors="coerce",
    )
    mask = dates.notna() & values.notna()

    series = _clean_series(
        dates[mask],
        values[mask],
        name="AUD",
    )
    if series.empty:
        raise ValueError("RBA FCMYGBAG2D yielded no observations.")

    return series


def fetch_aud_2y_v3163() -> YieldSeriesResult:
    raw = _http_get_bytes_browser(
        AUD_URL_V3162,
        timeout=30,
        referer="https://www.rba.gov.au/statistics/tables/",
    )
    series = _validate_official_series(
        _parse_rba_2y_v3163(raw),
        currency="AUD",
    )

    return YieldSeriesResult(
        "AUD",
        "Australian Government 2Y",
        "Reserve Bank of Australia",
        AUD_URL_V3162,
        series,
        note=(
            "Official RBA F2 exact series FCMYGBAG2D. "
            "Ragged CSV rows are parsed safely; observations are daily "
            "with the RBA publication lag."
        ),
    )


def _parse_rbnz_2y_v3163(raw: bytes) -> pd.Series:
    """Resolve the exact B2 2Y government-bond column from current XLSX."""
    best = pd.Series(dtype=float, name="NZD")
    best_count = 0

    for frame in _read_excel_candidates(raw):
        if frame is None or frame.empty:
            continue

        for r in range(min(len(frame), 60)):
            row_labels = [
                re.sub(
                    r"\s+",
                    " ",
                    str(
                        frame.iat[r, c]
                        if pd.notna(frame.iat[r, c])
                        else ""
                    ).strip().lower(),
                )
                for c in range(frame.shape[1])
            ]

            # Locate a maturity-header row containing the official benchmark set.
            if not any(label in {"1 year", "1 yr"} for label in row_labels):
                continue
            if not any(label in {"2 year", "2 yr"} for label in row_labels):
                continue
            if not any(label in {"5 year", "5 yr"} for label in row_labels):
                continue
            if not any(label in {"10 year", "10 yr"} for label in row_labels):
                continue

            value_col = next(
                (
                    c
                    for c, label in enumerate(row_labels)
                    if label in {"2 year", "2 yr"}
                ),
                None,
            )
            if value_col is None:
                continue

            context = " ".join(
                str(
                    frame.iat[rr, cc]
                    if pd.notna(frame.iat[rr, cc])
                    else ""
                ).lower()
                for rr in range(max(0, r - 6), r + 1)
                for cc in range(frame.shape[1])
            )

            if "government" not in context or "bond" not in context:
                continue

            start = r + 1
            work = frame.iloc[start:].reset_index(drop=True)

            date_col = None
            dates = pd.Series(dtype="datetime64[ns]")
            date_count = 0

            for c in range(work.shape[1]):
                parsed = _real_date_series(work.iloc[:, c])
                count = int(parsed.notna().sum())
                if count > date_count:
                    date_col = int(c)
                    dates = parsed
                    date_count = count

            if date_col is None or date_count < 20:
                continue

            values = pd.to_numeric(
                work.iloc[:, value_col],
                errors="coerce",
            )
            mask = dates.notna() & values.notna()

            candidate = _clean_series(
                dates[mask],
                values[mask],
                name="NZD",
            )
            if len(candidate) > best_count:
                best = candidate
                best_count = len(candidate)

    if best.empty:
        raise ValueError("RBNZ B2 exact 2Y government-bond series not found.")

    return best


def fetch_nzd_2y_v3163() -> YieldSeriesResult:
    raw = _http_get_bytes_browser(
        RBNZ_B2_URL_V3163,
        timeout=45,
        referer=(
            "https://www.rbnz.govt.nz/statistics/series/"
            "exchange-and-interest-rates/wholesale-interest-rates"
        ),
    )

    series = _validate_official_series(
        _parse_rbnz_2y_v3163(raw),
        currency="NZD",
    )

    return YieldSeriesResult(
        "NZD",
        "New Zealand Government 2Y",
        "Reserve Bank of New Zealand",
        RBNZ_B2_URL_V3163,
        series,
        note=(
            "Official RBNZ B2 Daily close 2Y secondary-market government "
            "bond yield. Browser-compatible request headers are used because "
            "the data-file host rejects the generic urllib client."
        ),
    )


# Keep the working USD/EUR/GBP/JPY adapters from V3.16.2.
FETCHERS = {
    "USD": fetch_usd_2y,
    "EUR": fetch_eur_2y_v3162,
    "GBP": fetch_gbp_2y_v3162,
    "JPY": fetch_jpy_2y_v3162,
    "CAD": fetch_cad_2y_v3163,
    "AUD": fetch_aud_2y_v3163,
    "NZD": fetch_nzd_2y_v3163,
}


def fetch_yield_universe() -> dict[str, YieldSeriesResult]:
    """V3.16.3 official-source universe."""
    results: dict[str, YieldSeriesResult] = {}

    for currency, fetcher in FETCHERS.items():
        try:
            item = fetcher()
            item.series = _validate_official_series(
                item.series,
                currency=currency,
            )
            item.status = "OK"
            results[currency] = item
        except Exception as exc:
            results[currency] = YieldSeriesResult(
                currency=currency,
                label=f"{currency} 2Y",
                source="Official source",
                source_url="",
                series=pd.Series(dtype=float, name=currency),
                status="ERROR",
                note=f"{type(exc).__name__}: {exc}",
            )

    for currency, (label, source, note) in UNAVAILABLE.items():
        results[currency] = YieldSeriesResult(
            currency=currency,
            label=label,
            source=source,
            source_url="",
            series=pd.Series(dtype=float, name=currency),
            status="N/V",
            note=note,
        )

    return results

# V3.16.4 · RBA 403 TRANSPORT FIX
import shutil
import subprocess


def _http_get_bytes_rba_v3164(
    url: str,
    timeout: int = 30,
) -> bytes:
    """Fetch the official RBA file with transport fallbacks.

    RBA may reject generic Python urllib clients with HTTP 403 even though the
    public F2 download is available in browsers. Keep the same official URL and
    only change the HTTP transport.
    """
    referer = "https://www.rba.gov.au/statistics/tables/"

    try:
        return _http_get_bytes_browser(
            url,
            timeout=timeout,
            referer=referer,
        )
    except HTTPError as exc:
        if int(getattr(exc, "code", 0) or 0) != 403:
            raise

    errors = []

    # Preferred Python fallback: libcurl with a browser TLS fingerprint.
    try:
        from curl_cffi import requests as curl_requests

        response = curl_requests.get(
            url,
            headers={
                "Referer": referer,
                "Accept": "text/csv,application/octet-stream,*/*",
                "Accept-Language": "en-AU,en;q=0.9",
            },
            impersonate="chrome",
            timeout=float(timeout),
            allow_redirects=True,
        )
        response.raise_for_status()
        content = bytes(response.content)
        if content:
            return content
        errors.append("curl_cffi returned empty content")
    except Exception as exc:
        errors.append(f"curl_cffi: {type(exc).__name__}: {exc}")

    # Last transport fallback for local macOS / standard Linux deployments.
    curl_bin = shutil.which("curl")
    if curl_bin:
        try:
            proc = subprocess.run(
                [
                    curl_bin,
                    "-L",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--compressed",
                    "--retry",
                    "2",
                    "--connect-timeout",
                    str(min(int(timeout), 15)),
                    "--max-time",
                    str(int(timeout)),
                    "-A",
                    (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0 Safari/537.36"
                    ),
                    "-e",
                    referer,
                    "-H",
                    "Accept: text/csv,application/octet-stream,*/*",
                    url,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            content = bytes(proc.stdout)
            if content:
                return content
            errors.append("system curl returned empty content")
        except Exception as exc:
            errors.append(f"system curl: {type(exc).__name__}: {exc}")
    else:
        errors.append("system curl not found")

    raise RuntimeError(
        "RBA F2 download blocked after all transport fallbacks. "
        + " | ".join(errors)
    )


def fetch_aud_2y_v3164() -> YieldSeriesResult:
    raw = _http_get_bytes_rba_v3164(
        AUD_URL_V3162,
        timeout=45,
    )
    series = _validate_official_series(
        _parse_rba_2y_v3163(raw),
        currency="AUD",
    )

    return YieldSeriesResult(
        "AUD",
        "Australian Government 2Y",
        "Reserve Bank of Australia",
        AUD_URL_V3162,
        series,
        note=(
            "Official RBA F2 exact series FCMYGBAG2D. "
            "If the RBA rejects Python urllib with HTTP 403, the same official "
            "download is retried through browser-compatible libcurl transport."
        ),
    )


# Keep every working adapter and replace only AUD transport.
FETCHERS = {
    "USD": fetch_usd_2y,
    "EUR": fetch_eur_2y_v3162,
    "GBP": fetch_gbp_2y_v3162,
    "JPY": fetch_jpy_2y_v3162,
    "CAD": fetch_cad_2y_v3163,
    "AUD": fetch_aud_2y_v3164,
    "NZD": fetch_nzd_2y_v3163,
}


def fetch_yield_universe() -> dict[str, YieldSeriesResult]:
    """V3.16.4 official-source universe with RBA transport fallback."""
    results: dict[str, YieldSeriesResult] = {}

    for currency, fetcher in FETCHERS.items():
        try:
            item = fetcher()
            item.series = _validate_official_series(
                item.series,
                currency=currency,
            )
            item.status = "OK"
            results[currency] = item
        except Exception as exc:
            results[currency] = YieldSeriesResult(
                currency=currency,
                label=f"{currency} 2Y",
                source="Official source",
                source_url="",
                series=pd.Series(dtype=float, name=currency),
                status="ERROR",
                note=f"{type(exc).__name__}: {exc}",
            )

    for currency, (label, source, note) in UNAVAILABLE.items():
        results[currency] = YieldSeriesResult(
            currency=currency,
            label=label,
            source=source,
            source_url="",
            series=pd.Series(dtype=float, name=currency),
            status="N/V",
            note=note,
        )

    return results
