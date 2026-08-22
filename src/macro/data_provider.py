
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import sqlite3
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .config import MacroConfig, SERIES_SPECS
from .types import SeriesSpec


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


@dataclass
class SeriesStatus:
    key: str
    series_id: str
    status: str
    rows: int
    cache_used: bool
    note: str = ""


class MacroCache:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    series_id TEXT NOT NULL,
                    observation_date TEXT NOT NULL,
                    availability_date TEXT NOT NULL,
                    value REAL NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY(series_id, observation_date)
                );

                CREATE TABLE IF NOT EXISTS series_meta (
                    series_id TEXT PRIMARY KEY,
                    fetched_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                );
                """
            )

    def upsert(self, spec: SeriesSpec, frame: pd.DataFrame):
        if frame is None or frame.empty:
            return

        fetched_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                spec.series_id,
                pd.Timestamp(row.observation_date).date().isoformat(),
                pd.Timestamp(row.availability_date).date().isoformat(),
                float(row.value),
                spec.provider,
                fetched_at,
            )
            for row in frame.itertuples(index=False)
        ]

        with self._connect() as con:
            con.executemany(
                """
                INSERT INTO observations(
                    series_id, observation_date, availability_date,
                    value, source, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_id, observation_date) DO UPDATE SET
                    availability_date=excluded.availability_date,
                    value=excluded.value,
                    source=excluded.source,
                    fetched_at=excluded.fetched_at
                """,
                rows,
            )
            con.execute(
                """
                INSERT INTO series_meta(series_id, fetched_at, row_count)
                VALUES (?, ?, ?)
                ON CONFLICT(series_id) DO UPDATE SET
                    fetched_at=excluded.fetched_at,
                    row_count=excluded.row_count
                """,
                (spec.series_id, fetched_at, len(rows)),
            )

    def load(self, spec: SeriesSpec) -> pd.DataFrame:
        with self._connect() as con:
            frame = pd.read_sql_query(
                """
                SELECT observation_date, availability_date, value, source, fetched_at
                FROM observations
                WHERE series_id=?
                ORDER BY observation_date
                """,
                con,
                params=(spec.series_id,),
            )

        if frame.empty:
            return frame

        frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
        frame["availability_date"] = pd.to_datetime(frame["availability_date"], errors="coerce")
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        return frame.dropna(subset=["observation_date", "availability_date", "value"])

    def age_hours(self, spec: SeriesSpec) -> float | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT fetched_at FROM series_meta WHERE series_id=?",
                (spec.series_id,),
            ).fetchone()

        if not row:
            return None

        try:
            then = datetime.fromisoformat(str(row[0]))
            if then.tzinfo is None:
                then = then.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (datetime.now(timezone.utc) - then).total_seconds() / 3600.0,
            )
        except Exception:
            return None


class FREDProvider:
    def __init__(
        self,
        config: MacroConfig,
        *,
        downloader: Callable[[str, float], bytes] | None = None,
    ):
        cache_cfg = config.section("cache")
        self.timeout = float(cache_cfg.get("timeout_seconds", 20.0))
        self.ttl_hours = float(cache_cfg.get("ttl_hours", 12.0))
        self.cache = MacroCache(
            cache_cfg.get(
                "path",
                ".cache/macro_model_library/v3240_macro.sqlite3",
            )
        )
        self.downloader = downloader or self._download

    @staticmethod
    def _download(url: str, timeout: float) -> bytes:
        req = Request(
            url,
            headers={
                "User-Agent": "COT-Research-Macro-Navigation/3.24",
                "Accept": "text/csv,*/*",
            },
        )
        with urlopen(req, timeout=float(timeout)) as response:
            return response.read()

    @staticmethod
    def parse_csv(payload: bytes, spec: SeriesSpec) -> pd.DataFrame:
        raw = pd.read_csv(StringIO(payload.decode("utf-8", errors="replace")))
        if raw.empty:
            return pd.DataFrame()

        date_col = next(
            (
                c
                for c in raw.columns
                if str(c).strip().upper() in {"DATE", "OBSERVATION_DATE"}
            ),
            raw.columns[0],
        )
        value_col = (
            spec.series_id
            if spec.series_id in raw.columns
            else next((c for c in raw.columns if c != date_col), None)
        )
        if value_col is None:
            return pd.DataFrame()

        frame = pd.DataFrame(
            {
                "observation_date": pd.to_datetime(raw[date_col], errors="coerce"),
                "value": pd.to_numeric(
                    raw[value_col].replace(".", pd.NA),
                    errors="coerce",
                ),
            }
        ).dropna()

        frame = (
            frame.sort_values("observation_date")
            .drop_duplicates("observation_date", keep="last")
        )
        frame = frame[
            frame["observation_date"] >= pd.Timestamp(spec.history_start)
        ].copy()

        frame["availability_date"] = (
            frame["observation_date"]
            + pd.to_timedelta(int(spec.release_lag_days), unit="D")
        )

        return frame[
            ["observation_date", "availability_date", "value"]
        ].reset_index(drop=True)

    def fetch(
        self,
        spec: SeriesSpec,
        *,
        force_refresh: bool = False,
    ) -> tuple[pd.DataFrame, SeriesStatus]:
        if not spec.enabled or not spec.series_id:
            return pd.DataFrame(), SeriesStatus(
                spec.key,
                spec.series_id,
                "DISABLED",
                0,
                False,
                spec.note,
            )

        cached = self.cache.load(spec)
        age = self.cache.age_hours(spec)

        if (
            not force_refresh
            and not cached.empty
            and age is not None
            and age <= self.ttl_hours
        ):
            return cached, SeriesStatus(
                spec.key, spec.series_id, "CACHE_FRESH", len(cached), True
            )

        try:
            payload = self.downloader(
                FRED_CSV_URL.format(series_id=spec.series_id),
                self.timeout,
            )
            frame = self.parse_csv(payload, spec)
            if frame.empty:
                raise ValueError("empty FRED series")
            self.cache.upsert(spec, frame)
            loaded = self.cache.load(spec)
            return loaded, SeriesStatus(
                spec.key, spec.series_id, "OK", len(loaded), False
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            if not cached.empty:
                return cached, SeriesStatus(
                    spec.key,
                    spec.series_id,
                    "CACHE_FALLBACK",
                    len(cached),
                    True,
                    str(exc),
                )

            return pd.DataFrame(), SeriesStatus(
                spec.key,
                spec.series_id,
                "OPTIONAL_MISSING" if not spec.required else "ERROR",
                0,
                False,
                str(exc),
            )

    def fetch_all(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, SeriesStatus]]:
        frames: dict[str, pd.DataFrame] = {}
        status: dict[str, SeriesStatus] = {}

        for spec in SERIES_SPECS:
            frame, item = self.fetch(
                spec,
                force_refresh=force_refresh,
            )
            frames[spec.key] = frame
            status[spec.key] = item

        return frames, status
