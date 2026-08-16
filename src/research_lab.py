
from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import cot_index
from .publication import backtest_available_date


UPPER_LABEL = "OBERES EXTREM"
LOWER_LABEL = "UNTERES EXTREM"


def positioning_series(
    enriched: pd.DataFrame,
    group_key: str,
    basis: str = "net_oi",
) -> pd.Series:
    """
    Return the selected positioning series.

    basis:
      - "net_oi": (Long - Short) / Open Interest
      - "raw":    Long - Short
    """
    if basis == "net_oi":
        col = f"{group_key}_net_oi"
    elif basis == "raw":
        col = f"{group_key}_net"
    else:
        raise ValueError(f"Unbekannte Basis: {basis}")

    if col not in enriched.columns:
        raise KeyError(f"Spalte fehlt: {col}")

    return pd.to_numeric(enriched[col], errors="coerce")


def extreme_zone(
    index_series: pd.Series,
    upper: float = 80.0,
    lower: float = 20.0,
) -> pd.Series:
    values = pd.to_numeric(index_series, errors="coerce")
    zone = np.where(
        values >= upper,
        1,
        np.where(values <= lower, -1, 0),
    )
    zone = pd.Series(zone, index=index_series.index, dtype="int64")
    zone[values.isna()] = 0
    return zone


def extract_extreme_episodes(
    report_dates: pd.Series,
    index_series: pd.Series,
    upper: float = 80.0,
    lower: float = 20.0,
) -> pd.DataFrame:
    """
    Consecutive weeks in the same upper/lower extreme form one episode.
    A release is the first following report that is no longer in that
    same extreme zone.
    """
    dates = pd.to_datetime(report_dates).reset_index(drop=True)
    idx = pd.to_numeric(index_series, errors="coerce").reset_index(drop=True)
    zones = extreme_zone(idx, upper=upper, lower=lower).to_numpy(dtype=int)

    rows = []
    i = 0
    n = len(idx)

    while i < n:
        zone = int(zones[i])
        if zone == 0:
            i += 1
            continue

        start = i
        while i + 1 < n and int(zones[i + 1]) == zone:
            i += 1
        end = i

        release_pos = end + 1 if end + 1 < n else np.nan
        release_date = (
            dates.iloc[int(release_pos)]
            if np.isfinite(release_pos)
            else pd.NaT
        )

        ep_idx = idx.iloc[start:end + 1]
        if zone > 0:
            extreme_value = float(ep_idx.max())
        else:
            extreme_value = float(ep_idx.min())

        rows.append({
            "zone": zone,
            "zone_label": UPPER_LABEL if zone > 0 else LOWER_LABEL,
            "entry_pos": int(start),
            "end_pos": int(end),
            "release_pos": release_pos,
            "entry_report_date": dates.iloc[start],
            "last_extreme_report_date": dates.iloc[end],
            "release_report_date": release_date,
            "duration_weeks": int(end - start + 1),
            "extreme_index": extreme_value,
        })

        i += 1

    return pd.DataFrame(rows)


def _price_arrays(prices: pd.DataFrame):
    if prices is None or prices.empty or "close" not in prices.columns:
        return np.asarray([], dtype="datetime64[ns]"), np.asarray([], dtype=float)

    p = prices[["close"]].copy().dropna().sort_index()
    p.index = pd.to_datetime(p.index)
    if getattr(p.index, "tz", None) is not None:
        p.index = p.index.tz_localize(None)

    return (
        p.index.to_numpy(dtype="datetime64[ns]"),
        p["close"].to_numpy(dtype=float),
    )


def _price_on_or_after(
    price_dates: np.ndarray,
    price_close: np.ndarray,
    target,
):
    if len(price_dates) == 0:
        return pd.NaT, np.nan

    ts = np.datetime64(pd.Timestamp(target).to_datetime64())
    pos = int(np.searchsorted(price_dates, ts, side="left"))
    if pos >= len(price_dates):
        return pd.NaT, np.nan

    return pd.Timestamp(price_dates[pos]), float(price_close[pos])


def _price_strictly_after(
    price_dates: np.ndarray,
    price_close: np.ndarray,
    target,
):
    if len(price_dates) == 0:
        return pd.NaT, np.nan

    ts = np.datetime64(pd.Timestamp(target).to_datetime64())
    pos = int(np.searchsorted(price_dates, ts, side="right"))
    if pos >= len(price_dates):
        return pd.NaT, np.nan

    return pd.Timestamp(price_dates[pos]), float(price_close[pos])


def forward_return_from_report(
    prices: pd.DataFrame,
    report_date,
    horizon_weeks: int,
) -> dict:
    """
    Publication-lag aware return.

    The entry is the first available daily close strictly after the
    conservative information-availability anchor.
    """
    dates, close = _price_arrays(prices)
    if len(dates) == 0:
        return {
            "trade_date": pd.NaT,
            "entry_price": np.nan,
            "exit_date": pd.NaT,
            "exit_price": np.nan,
            "return": np.nan,
        }

    available = backtest_available_date(report_date)
    trade_date, entry = _price_strictly_after(dates, close, available)

    if not np.isfinite(entry) or pd.isna(trade_date):
        return {
            "trade_date": pd.NaT,
            "entry_price": np.nan,
            "exit_date": pd.NaT,
            "exit_price": np.nan,
            "return": np.nan,
        }

    target = trade_date + pd.Timedelta(weeks=int(horizon_weeks))
    exit_date, exit_price = _price_on_or_after(dates, close, target)

    if not np.isfinite(exit_price):
        ret = np.nan
    else:
        ret = exit_price / entry - 1.0

    return {
        "trade_date": trade_date,
        "entry_price": entry,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "return": ret,
    }


def _events_for_index(
    report_dates: pd.Series,
    index_series: pd.Series,
    prices: pd.DataFrame,
    index_weeks: int,
    horizons=(4, 8),
    upper: float = 80.0,
    lower: float = 20.0,
    polarity: int = 0,
) -> pd.DataFrame:
    """
    Event rows for both new extreme entries and releases.

    polarity:
      +1: upper extreme/release is interpreted bullish, lower bearish
       0: no directional interpretation
      -1: upper is interpreted bearish, lower bullish
    """
    episodes = extract_extreme_episodes(
        report_dates,
        index_series,
        upper=upper,
        lower=lower,
    )
    if episodes.empty:
        return pd.DataFrame()

    rows = []

    for _, ep in episodes.iterrows():
        for event_type, report_date in (
            ("EXTREM-EINTRITT", ep["entry_report_date"]),
            ("RELEASE", ep["release_report_date"]),
        ):
            if pd.isna(report_date):
                continue

            rec = {
                "index_weeks": int(index_weeks),
                "event_type": event_type,
                "zone": int(ep["zone"]),
                "zone_label": ep["zone_label"],
                "event_report_date": pd.Timestamp(report_date),
                "episode_duration": int(ep["duration_weeks"]),
                "extreme_index": float(ep["extreme_index"]),
            }

            if polarity:
                rec["expected_direction"] = int(ep["zone"]) * int(polarity)
            else:
                rec["expected_direction"] = np.nan

            for h in horizons:
                fwd = forward_return_from_report(
                    prices,
                    report_date,
                    int(h),
                )
                rec[f"trade_date_{h}w"] = fwd["trade_date"]
                rec[f"return_{h}w"] = fwd["return"]

                if polarity and np.isfinite(fwd["return"]):
                    rec[f"directional_return_{h}w"] = (
                        fwd["return"] * rec["expected_direction"]
                    )
                else:
                    rec[f"directional_return_{h}w"] = np.nan

            rows.append(rec)

    return pd.DataFrame(rows)


def index_window_comparison(
    enriched: pd.DataFrame,
    group_key: str,
    basis: str,
    prices: pd.DataFrame,
    windows=(26, 52),
    horizons=(4, 8),
    upper: float = 80.0,
    lower: float = 20.0,
    polarity: int = 0,
) -> dict:
    series = positioning_series(enriched, group_key, basis=basis)
    report_dates = pd.to_datetime(enriched["report_date"])

    indexes = {
        int(w): cot_index(series, int(w))
        for w in windows
    }
    zones = {
        int(w): extreme_zone(indexes[int(w)], upper=upper, lower=lower)
        for w in windows
    }

    w1, w2 = [int(x) for x in windows]
    valid = indexes[w1].notna() & indexes[w2].notna()
    z1 = zones[w1][valid]
    z2 = zones[w2][valid]

    e1 = z1 != 0
    e2 = z2 != 0
    both = e1 & e2
    same = both & (z1 == z2)

    overlap = {
        "valid_weeks": int(valid.sum()),
        f"extreme_weeks_{w1}": int(e1.sum()),
        f"extreme_weeks_{w2}": int(e2.sum()),
        "both_extreme_weeks": int(both.sum()),
        "same_direction_weeks": int(same.sum()),
        f"p_{w2}_given_{w1}": (
            float(both.sum() / e1.sum())
            if e1.sum() else np.nan
        ),
        f"p_{w1}_given_{w2}": (
            float(both.sum() / e2.sum())
            if e2.sum() else np.nan
        ),
        "direction_agreement_when_both": (
            float(same.sum() / both.sum())
            if both.sum() else np.nan
        ),
    }

    episode_rows = []
    event_frames = []

    for w in (w1, w2):
        eps = extract_extreme_episodes(
            report_dates,
            indexes[w],
            upper=upper,
            lower=lower,
        )
        episode_rows.append({
            "Indexfenster": f"{w}W",
            "Extreme Wochen": int((zones[w] != 0).sum()),
            "Extreme Episoden": int(len(eps)),
            "Median Episodendauer": (
                float(eps["duration_weeks"].median())
                if not eps.empty else np.nan
            ),
            "Obere Episoden": (
                int((eps["zone"] == 1).sum())
                if not eps.empty else 0
            ),
            "Untere Episoden": (
                int((eps["zone"] == -1).sum())
                if not eps.empty else 0
            ),
            "Releases": (
                int(eps["release_report_date"].notna().sum())
                if not eps.empty else 0
            ),
        })

        events = _events_for_index(
            report_dates,
            indexes[w],
            prices,
            index_weeks=w,
            horizons=horizons,
            upper=upper,
            lower=lower,
            polarity=polarity,
        )
        if not events.empty:
            event_frames.append(events)

    all_events = (
        pd.concat(event_frames, ignore_index=True)
        if event_frames
        else pd.DataFrame()
    )

    summary_rows = []

    if not all_events.empty:
        for w in (w1, w2):
            for event_type in ("EXTREM-EINTRITT", "RELEASE"):
                subset = all_events[
                    (all_events["index_weeks"] == w)
                    & (all_events["event_type"] == event_type)
                ]

                for h in horizons:
                    raw = pd.to_numeric(
                        subset[f"return_{h}w"],
                        errors="coerce",
                    )
                    upper_raw = pd.to_numeric(
                        subset.loc[
                            subset["zone"] == 1,
                            f"return_{h}w",
                        ],
                        errors="coerce",
                    ).dropna()
                    lower_raw = pd.to_numeric(
                        subset.loc[
                            subset["zone"] == -1,
                            f"return_{h}w",
                        ],
                        errors="coerce",
                    ).dropna()

                    directional = pd.to_numeric(
                        subset[f"directional_return_{h}w"],
                        errors="coerce",
                    ).dropna()

                    summary_rows.append({
                        "Indexfenster": f"{w}W",
                        "Event": event_type,
                        "Horizont": f"{h}W",
                        "n": int(raw.notna().sum()),
                        "Upper n": int(len(upper_raw)),
                        "Upper Median": (
                            float(upper_raw.median())
                            if len(upper_raw) else np.nan
                        ),
                        "Lower n": int(len(lower_raw)),
                        "Lower Median": (
                            float(lower_raw.median())
                            if len(lower_raw) else np.nan
                        ),
                        "Dir. Hit Rate": (
                            float((directional > 0).mean())
                            if len(directional) else np.nan
                        ),
                        "Dir. Median": (
                            float(directional.median())
                            if len(directional) else np.nan
                        ),
                        "Dir. Mittel": (
                            float(directional.mean())
                            if len(directional) else np.nan
                        ),
                    })

    return {
        "series": series,
        "indexes": indexes,
        "overlap": overlap,
        "episodes": pd.DataFrame(episode_rows),
        "events": all_events,
        "event_summary": pd.DataFrame(summary_rows),
    }


def release_decay_study(
    enriched: pd.DataFrame,
    group_key: str,
    basis: str,
    prices: pd.DataFrame,
    index_windows=(26, 52),
    delays=(0, 1, 2, 3, 4),
    horizons=(4, 8),
    upper: float = 80.0,
    lower: float = 20.0,
    polarity: int = 0,
) -> dict:
    """
    Measure the outcome of entering 0..4 weeks after an observed release.
    The delay starts from the first tradeable date after the release became
    public, not from the Tuesday positioning date.
    """
    series = positioning_series(enriched, group_key, basis=basis)
    report_dates = pd.to_datetime(enriched["report_date"])
    price_dates, price_close = _price_arrays(prices)

    event_rows = []

    for w in index_windows:
        idx = cot_index(series, int(w))
        episodes = extract_extreme_episodes(
            report_dates,
            idx,
            upper=upper,
            lower=lower,
        )

        for _, ep in episodes.iterrows():
            release_report = ep["release_report_date"]
            if pd.isna(release_report):
                continue

            available = backtest_available_date(release_report)
            base_trade_date, base_entry = _price_strictly_after(
                price_dates,
                price_close,
                available,
            )
            if not np.isfinite(base_entry) or pd.isna(base_trade_date):
                continue

            expected_direction = (
                int(ep["zone"]) * int(polarity)
                if polarity else np.nan
            )

            for delay in delays:
                delayed_target = (
                    base_trade_date
                    + pd.Timedelta(weeks=int(delay))
                )
                delayed_trade, delayed_entry = _price_on_or_after(
                    price_dates,
                    price_close,
                    delayed_target,
                )
                if not np.isfinite(delayed_entry):
                    continue

                rec = {
                    "index_weeks": int(w),
                    "zone": int(ep["zone"]),
                    "zone_label": ep["zone_label"],
                    "release_report_date": pd.Timestamp(release_report),
                    "base_trade_date": base_trade_date,
                    "delay_weeks": int(delay),
                    "trade_date": delayed_trade,
                    "episode_duration": int(ep["duration_weeks"]),
                    "expected_direction": expected_direction,
                }

                for h in horizons:
                    target = delayed_trade + pd.Timedelta(weeks=int(h))
                    exit_date, exit_price = _price_on_or_after(
                        price_dates,
                        price_close,
                        target,
                    )
                    if np.isfinite(exit_price):
                        raw_return = exit_price / delayed_entry - 1.0
                    else:
                        raw_return = np.nan

                    rec[f"return_{h}w"] = raw_return
                    rec[f"exit_date_{h}w"] = exit_date

                    if polarity and np.isfinite(raw_return):
                        rec[f"directional_return_{h}w"] = (
                            raw_return * expected_direction
                        )
                    else:
                        rec[f"directional_return_{h}w"] = np.nan

                event_rows.append(rec)

    events = pd.DataFrame(event_rows)
    summary_rows = []

    if not events.empty:
        for w in index_windows:
            for delay in delays:
                subset = events[
                    (events["index_weeks"] == int(w))
                    & (events["delay_weeks"] == int(delay))
                ]

                for h in horizons:
                    upper_raw = pd.to_numeric(
                        subset.loc[
                            subset["zone"] == 1,
                            f"return_{h}w",
                        ],
                        errors="coerce",
                    ).dropna()
                    lower_raw = pd.to_numeric(
                        subset.loc[
                            subset["zone"] == -1,
                            f"return_{h}w",
                        ],
                        errors="coerce",
                    ).dropna()
                    directional = pd.to_numeric(
                        subset[f"directional_return_{h}w"],
                        errors="coerce",
                    ).dropna()

                    summary_rows.append({
                        "Indexfenster": f"{int(w)}W",
                        "Einstieg nach Release": f"W{int(delay)}",
                        "Horizont": f"{int(h)}W",
                        "n": int(
                            pd.to_numeric(
                                subset[f"return_{h}w"],
                                errors="coerce",
                            ).notna().sum()
                        ),
                        "Upper Median": (
                            float(upper_raw.median())
                            if len(upper_raw) else np.nan
                        ),
                        "Lower Median": (
                            float(lower_raw.median())
                            if len(lower_raw) else np.nan
                        ),
                        "Dir. Hit Rate": (
                            float((directional > 0).mean())
                            if len(directional) else np.nan
                        ),
                        "Dir. Median": (
                            float(directional.median())
                            if len(directional) else np.nan
                        ),
                        "Dir. Mittel": (
                            float(directional.mean())
                            if len(directional) else np.nan
                        ),
                    })

    return {
        "events": events,
        "summary": pd.DataFrame(summary_rows),
    }


def _forward_return_lookup(
    report_dates: pd.Series,
    prices: pd.DataFrame,
    horizon_weeks: int,
) -> np.ndarray:
    out = np.full(len(report_dates), np.nan, dtype=float)

    for i, report_date in enumerate(pd.to_datetime(report_dates)):
        result = forward_return_from_report(
            prices,
            report_date,
            horizon_weeks=int(horizon_weeks),
        )
        out[i] = result["return"]

    return out


def circular_shift_null_model(
    enriched: pd.DataFrame,
    group_key: str,
    basis: str,
    prices: pd.DataFrame,
    index_weeks: int = 26,
    event_type: str = "RELEASE",
    horizon_weeks: int = 8,
    upper: float = 80.0,
    lower: float = 20.0,
    polarity: int = 0,
    simulations: int = 2000,
    seed: int = 42,
) -> dict:
    """
    Per-market timing null model using one circular shift for the entire
    event schedule in each simulation.

    This preserves event spacing, clustering and event directions while
    destroying the original timing relation to subsequent price returns.

    It does NOT by itself solve family-wise multiple testing across the
    complete market universe.
    """
    if polarity == 0:
        raise ValueError(
            "Für diese Tradergruppe ist keine Richtungs-Konvention definiert."
        )

    series = positioning_series(enriched, group_key, basis=basis)
    report_dates = pd.to_datetime(enriched["report_date"]).reset_index(drop=True)
    idx = cot_index(series, int(index_weeks))
    episodes = extract_extreme_episodes(
        report_dates,
        idx,
        upper=upper,
        lower=lower,
    )

    if episodes.empty:
        return {
            "observed_n": 0,
            "null": pd.DataFrame(),
        }

    event_positions = []
    event_directions = []

    for _, ep in episodes.iterrows():
        if event_type == "EXTREM-EINTRITT":
            pos = int(ep["entry_pos"])
        elif event_type == "RELEASE":
            if not np.isfinite(ep["release_pos"]):
                continue
            pos = int(ep["release_pos"])
        else:
            raise ValueError(f"Unbekannter Event-Typ: {event_type}")

        event_positions.append(pos)
        event_directions.append(int(ep["zone"]) * int(polarity))

    if not event_positions:
        return {
            "observed_n": 0,
            "null": pd.DataFrame(),
        }

    event_positions = np.asarray(event_positions, dtype=int)
    event_directions = np.asarray(event_directions, dtype=float)

    forward = _forward_return_lookup(
        report_dates,
        prices,
        horizon_weeks=int(horizon_weeks),
    )

    observed_raw = forward[event_positions]
    observed_directional = observed_raw * event_directions
    observed_directional = observed_directional[
        np.isfinite(observed_directional)
    ]

    if len(observed_directional) == 0:
        return {
            "observed_n": 0,
            "null": pd.DataFrame(),
        }

    observed_hit = float(np.mean(observed_directional > 0))
    observed_median = float(np.median(observed_directional))
    observed_mean = float(np.mean(observed_directional))

    n_rows = len(report_dates)
    rng = np.random.default_rng(int(seed))
    null_rows = []

    valid_shifts = np.arange(1, n_rows, dtype=int)
    if len(valid_shifts) == 0:
        return {
            "observed_n": len(observed_directional),
            "observed_hit_rate": observed_hit,
            "observed_median": observed_median,
            "observed_mean": observed_mean,
            "null": pd.DataFrame(),
        }

    for _ in range(int(simulations)):
        shift = int(rng.choice(valid_shifts))
        shifted_pos = (event_positions + shift) % n_rows
        shifted_raw = forward[shifted_pos]
        shifted_directional = shifted_raw * event_directions
        shifted_directional = shifted_directional[
            np.isfinite(shifted_directional)
        ]

        if len(shifted_directional) == 0:
            continue

        null_rows.append({
            "shift": shift,
            "n": int(len(shifted_directional)),
            "hit_rate": float(np.mean(shifted_directional > 0)),
            "median_return": float(np.median(shifted_directional)),
            "mean_return": float(np.mean(shifted_directional)),
        })

    null = pd.DataFrame(null_rows)

    if null.empty:
        return {
            "observed_n": int(len(observed_directional)),
            "observed_hit_rate": observed_hit,
            "observed_median": observed_median,
            "observed_mean": observed_mean,
            "null": null,
        }

    def q(series, p):
        return float(np.quantile(series.dropna(), p))

    hit_p = float(
        (1 + np.sum(null["hit_rate"] >= observed_hit))
        / (1 + len(null))
    )
    median_p = float(
        (1 + np.sum(null["median_return"] >= observed_median))
        / (1 + len(null))
    )

    return {
        "observed_n": int(len(observed_directional)),
        "observed_hit_rate": observed_hit,
        "observed_median": observed_median,
        "observed_mean": observed_mean,
        "null_hit_median": float(null["hit_rate"].median()),
        "null_hit_low": q(null["hit_rate"], 0.025),
        "null_hit_high": q(null["hit_rate"], 0.975),
        "hit_empirical_p": hit_p,
        "null_median_return": float(null["median_return"].median()),
        "null_return_low": q(null["median_return"], 0.025),
        "null_return_high": q(null["median_return"], 0.975),
        "median_empirical_p": median_p,
        "null": null,
    }
