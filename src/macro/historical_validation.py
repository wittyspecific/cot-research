from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class RecessionEpisode:
    start: pd.Timestamp
    end: pd.Timestamp

    @property
    def label(self) -> str:
        if self.start.year == self.end.year:
            return f"{self.start.year}"
        return f"{self.start.year}–{self.end.year}"


def recession_episodes_from_usrec(
    usrec_frame: pd.DataFrame,
    *,
    start_year: int = 1990,
) -> list[RecessionEpisode]:
    """Convert monthly USREC into recession episodes for ex-post validation."""
    if usrec_frame is None or usrec_frame.empty:
        return []

    work = usrec_frame[["observation_date", "value"]].copy()
    work["observation_date"] = pd.to_datetime(
        work["observation_date"],
        errors="coerce",
    )
    work["value"] = pd.to_numeric(
        work["value"],
        errors="coerce",
    )
    work = (
        work.dropna()
        .sort_values("observation_date")
        .drop_duplicates("observation_date", keep="last")
    )
    work = work[
        work["observation_date"].dt.year >= int(start_year)
    ].copy()

    if work.empty:
        return []

    episodes = []
    start = None
    last_active = None

    for row in work.itertuples(index=False):
        date = pd.Timestamp(row.observation_date).normalize()
        active = float(row.value) >= 0.5

        if active and start is None:
            start = date
        if active:
            last_active = date
        elif start is not None:
            end = (
                pd.Timestamp(last_active)
                + pd.offsets.MonthEnd(1)
            ).normalize()
            episodes.append(
                RecessionEpisode(
                    start=start,
                    end=end,
                )
            )
            start = None
            last_active = None

    if start is not None and last_active is not None:
        episodes.append(
            RecessionEpisode(
                start=start,
                end=(
                    pd.Timestamp(last_active)
                    + pd.offsets.MonthEnd(1)
                ).normalize(),
            )
        )

    return episodes


def _weekly_recession_mask(
    index: pd.DatetimeIndex,
    episodes: list[RecessionEpisode],
) -> pd.Series:
    mask = pd.Series(False, index=index, dtype=bool)
    for episode in episodes:
        mask.loc[
            (mask.index >= episode.start)
            & (mask.index <= episode.end)
        ] = True
    return mask


def _phase_at(
    cycle: pd.DataFrame,
    when: pd.Timestamp,
) -> str:
    subset = cycle.loc[
        cycle.index <= pd.Timestamp(when)
    ]
    if subset.empty:
        return "N/V"
    return str(
        subset.iloc[-1].get(
            "cycle_phase",
            "N/V",
        )
    )


def _latest_phase_onset_before(
    cycle: pd.DataFrame,
    phase: str,
    when: pd.Timestamp,
    *,
    lookback_weeks: int,
) -> pd.Timestamp | None:
    end = pd.Timestamp(when)
    start = end - pd.Timedelta(
        weeks=int(lookback_weeks)
    )
    series = cycle.loc[
        (cycle.index >= start)
        & (cycle.index <= end),
        "cycle_phase",
    ].astype(str)

    if series.empty:
        return None

    onset = series.eq(phase) & series.shift(1).ne(phase)
    hits = series.index[onset]
    return (
        pd.Timestamp(hits[-1])
        if len(hits)
        else None
    )


def _first_phase_near(
    cycle: pd.DataFrame,
    phase: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Timestamp | None:
    series = cycle.loc[
        (cycle.index >= pd.Timestamp(start))
        & (cycle.index <= pd.Timestamp(end)),
        "cycle_phase",
    ].astype(str)

    hits = series.index[series.eq(phase)]
    return (
        pd.Timestamp(hits[0])
        if len(hits)
        else None
    )


def _weeks(delta: pd.Timedelta) -> float:
    return float(
        delta.total_seconds()
        / (7.0 * 24.0 * 3600.0)
    )


def evaluate_historical_cycle(
    *,
    cycle_history: pd.DataFrame,
    usrec_frame: pd.DataFrame,
    start_year: int = 1990,
) -> dict[str, Any]:
    """
    Retrospective measurement only.

    Results never feed back into cycle classification or threshold fitting.
    """
    episodes = recession_episodes_from_usrec(
        usrec_frame,
        start_year=start_year,
    )

    if cycle_history is None or cycle_history.empty:
        return {
            "mode": "RETROSPECTIVE_REVISED_DATA",
            "episodes": [],
            "summary": {},
            "warning": "No cycle history available for validation.",
        }

    cycle = cycle_history.copy()
    cycle.index = pd.to_datetime(
        cycle.index,
        errors="coerce",
    )
    cycle = cycle[
        ~cycle.index.isna()
    ].sort_index()

    if "cycle_phase" not in cycle.columns:
        return {
            "mode": "RETROSPECTIVE_REVISED_DATA",
            "episodes": [],
            "summary": {},
            "warning": "cycle_phase missing from cycle history.",
        }

    valid = cycle[
        cycle["cycle_phase"].astype(str)
        != "UNCERTAIN"
    ]
    first_valid = (
        pd.Timestamp(valid.index.min())
        if not valid.empty
        else None
    )

    rows = []

    for episode in episodes:
        evaluable = bool(
            first_valid is not None
            and first_valid
            <= episode.start - pd.Timedelta(weeks=13)
        )

        slowdown = (
            _latest_phase_onset_before(
                cycle,
                "SLOWDOWN",
                episode.start,
                lookback_weeks=104,
            )
            if evaluable
            else None
        )

        contraction = (
            _first_phase_near(
                cycle,
                "CONTRACTION",
                episode.start - pd.Timedelta(weeks=26),
                episode.end + pd.Timedelta(weeks=26),
            )
            if evaluable
            else None
        )

        recovery = (
            _first_phase_near(
                cycle,
                "RECOVERY",
                episode.start,
                episode.end + pd.Timedelta(weeks=52),
            )
            if evaluable
            else None
        )

        pre = cycle.loc[
            (cycle.index >= episode.start - pd.Timedelta(weeks=13))
            & (cycle.index < episode.start),
            "cycle_phase",
        ].astype(str)

        during = cycle.loc[
            (cycle.index >= episode.start)
            & (cycle.index <= episode.end),
            "cycle_phase",
        ].astype(str)

        rows.append(
            {
                "episode": episode.label,
                "start": episode.start.date().isoformat(),
                "end": episode.end.date().isoformat(),
                "evaluable": evaluable,
                "phase_at_start": (
                    _phase_at(cycle, episode.start)
                    if evaluable
                    else "N/V"
                ),
                "phase_at_end": (
                    _phase_at(cycle, episode.end)
                    if evaluable
                    else "N/V"
                ),
                "slowdown_onset": (
                    slowdown.date().isoformat()
                    if slowdown is not None
                    else None
                ),
                "slowdown_lead_weeks": (
                    _weeks(episode.start - slowdown)
                    if slowdown is not None
                    else None
                ),
                "contraction_first": (
                    contraction.date().isoformat()
                    if contraction is not None
                    else None
                ),
                "contraction_lag_weeks": (
                    _weeks(contraction - episode.start)
                    if contraction is not None
                    else None
                ),
                "recovery_first": (
                    recovery.date().isoformat()
                    if recovery is not None
                    else None
                ),
                "recovery_vs_end_weeks": (
                    _weeks(recovery - episode.end)
                    if recovery is not None
                    else None
                ),
                "pre13w_warning_share": (
                    float(
                        pre.isin(
                            ["SLOWDOWN", "CONTRACTION"]
                        ).mean()
                    )
                    if evaluable and not pre.empty
                    else None
                ),
                "contraction_overlap_share": (
                    float(
                        during.eq(
                            "CONTRACTION"
                        ).mean()
                    )
                    if evaluable and not during.empty
                    else None
                ),
            }
        )

    evaluable_rows = [
        row for row in rows if row["evaluable"]
    ]

    def finite_values(key):
        values = []
        for row in evaluable_rows:
            value = row.get(key)
            if value is None:
                continue
            value = float(value)
            if np.isfinite(value):
                values.append(value)
        return values

    slowdown_before = [
        row
        for row in evaluable_rows
        if (
            row.get("slowdown_lead_weeks") is not None
            and float(row["slowdown_lead_weeks"]) >= 0.0
        )
    ]

    contraction_near = [
        row
        for row in evaluable_rows
        if (
            row.get("contraction_lag_weeks") is not None
            and -13.0 <= float(row["contraction_lag_weeks"]) <= 13.0
        )
    ]

    recession_mask = _weekly_recession_mask(
        cycle.index,
        episodes,
    )
    phase = cycle["cycle_phase"].astype(str)
    evaluable_mask = phase.ne("UNCERTAIN")

    non_recession = (~recession_mask) & evaluable_mask
    recession_weeks = recession_mask & evaluable_mask

    summary = {
        "start_year": int(start_year),
        "episodes_total": len(rows),
        "episodes_evaluable": len(evaluable_rows),
        "slowdown_before_start_rate": (
            len(slowdown_before) / len(evaluable_rows)
            if evaluable_rows
            else None
        ),
        "contraction_near_start_rate": (
            len(contraction_near) / len(evaluable_rows)
            if evaluable_rows
            else None
        ),
        "median_slowdown_lead_weeks": (
            float(
                np.median(
                    finite_values(
                        "slowdown_lead_weeks"
                    )
                )
            )
            if finite_values("slowdown_lead_weeks")
            else None
        ),
        "median_contraction_lag_weeks": (
            float(
                np.median(
                    finite_values(
                        "contraction_lag_weeks"
                    )
                )
            )
            if finite_values("contraction_lag_weeks")
            else None
        ),
        "mean_contraction_overlap_share": (
            float(
                np.mean(
                    finite_values(
                        "contraction_overlap_share"
                    )
                )
            )
            if finite_values("contraction_overlap_share")
            else None
        ),
        "false_contraction_share_outside_recession": (
            float(
                phase.loc[
                    non_recession
                ].eq("CONTRACTION").mean()
            )
            if non_recession.any()
            else None
        ),
        "recession_week_contraction_recall": (
            float(
                phase.loc[
                    recession_weeks
                ].eq("CONTRACTION").mean()
            )
            if recession_weeks.any()
            else None
        ),
        "first_valid_cycle_date": (
            first_valid.date().isoformat()
            if first_valid is not None
            else None
        ),
    }

    return {
        "mode": "RETROSPECTIVE_REVISED_DATA",
        "episodes": rows,
        "summary": summary,
        "warning": (
            "Retrospective validation against USREC/NBER chronology using "
            "current/revised FRED history plus conservative release lags. "
            "This is not a true vintage or real-time backtest. Thresholds "
            "are not automatically refit from these episodes."
        ),
    }
