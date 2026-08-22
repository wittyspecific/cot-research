from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import MacroConfig
from .features import FeatureFrame
from .historical_validation import RecessionEpisode, recession_episodes_from_usrec


CANDIDATES = {
    "CURRENT": {"label": "Current V3.24", "logic": "COI Dist < -5 · Slope ≤ 0"},
    "A": {"label": "Candidate A", "logic": "COI Dist < -10 · Slope < 0 · Persistenz 3/4W"},
    "B": {"label": "Candidate B", "logic": "COI Dist < -15 · Slope < 0 · 3/4W · COI Family Breadth ≥ 50%"},
    "C": {"label": "Candidate C", "logic": "B + Employment Family bestätigt Risk-Off"},
    "D": {"label": "Candidate D", "logic": "COI Dist < -20 · 6/8W · ≥2 Coincident Families Risk-Off"},
}


def _classify_score(value: Any, threshold: float) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/V"
    if not np.isfinite(value):
        return "N/V"
    if value <= -abs(float(threshold)):
        return "RISK_OFF"
    if value >= abs(float(threshold)):
        return "RISK_ON"
    return "NEUTRAL"


def _coincident_family_history(
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
) -> pd.DataFrame:
    if weekly_scores is None or weekly_scores.empty:
        return pd.DataFrame()

    cfg = config.section("breadth")
    atomic_threshold = float(cfg.get("atomic_threshold", 20.0))
    family_threshold = float(cfg.get("family_agreement_threshold", 0.60))

    family_models: dict[str, list[str]] = {}
    for name, item in features.items():
        if item.spec.tier == "coincident" and name in weekly_scores.columns:
            family_models.setdefault(item.spec.family, []).append(name)

    out = pd.DataFrame(index=weekly_scores.index)

    for family, names in sorted(family_models.items()):
        states = []
        for _, row in weekly_scores[names].iterrows():
            signals = [
                _classify_score(row.get(name), atomic_threshold)
                for name in names
            ]
            signals = [signal for signal in signals if signal != "N/V"]
            if not signals:
                states.append("N/V")
                continue

            risk_off = signals.count("RISK_OFF")
            risk_on = signals.count("RISK_ON")
            active = len(signals)
            dominant = max(risk_off, risk_on)
            agreement = dominant / active if active else 0.0

            if risk_off > risk_on and agreement >= family_threshold:
                states.append("RISK_OFF")
            elif risk_on > risk_off and agreement >= family_threshold:
                states.append("RISK_ON")
            else:
                states.append("MIXED")

        out[family] = states

    available = out.ne("N/V").sum(axis=1)
    risk_off = out.eq("RISK_OFF").sum(axis=1)
    out["risk_off_family_count"] = risk_off
    out["available_family_count"] = available
    out["risk_off_breadth"] = risk_off / available.replace(0, np.nan)
    return out


def _persistence(condition: pd.Series, *, window: int, required: int) -> pd.Series:
    clean = condition.fillna(False).astype(bool)
    return (
        clean.astype(int)
        .rolling(int(window), min_periods=int(window))
        .sum()
        .ge(int(required))
    )


def build_candidate_series(
    *,
    cycle_history: pd.DataFrame,
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if cycle_history is None or cycle_history.empty:
        return pd.DataFrame(), pd.DataFrame()

    cycle = cycle_history.copy()
    cycle.index = pd.to_datetime(cycle.index, errors="coerce")
    cycle = cycle[~cycle.index.isna()].sort_index()

    family = _coincident_family_history(
        weekly_scores, features, config
    ).reindex(cycle.index)

    distance = pd.to_numeric(cycle.get("coincident_distance"), errors="coerce")
    slope = pd.to_numeric(cycle.get("coincident_slope_13w"), errors="coerce")

    current = distance.lt(-5.0) & slope.le(0.0)

    base_a = distance.lt(-10.0) & slope.lt(0.0)
    candidate_a = _persistence(base_a, window=4, required=3)

    base_b = (
        distance.lt(-15.0)
        & slope.lt(0.0)
        & family["risk_off_breadth"].ge(0.50)
    )
    candidate_b = _persistence(base_b, window=4, required=3)

    employment = (
        family["employment"].eq("RISK_OFF")
        if "employment" in family.columns
        else pd.Series(False, index=cycle.index)
    )
    candidate_c = _persistence(base_b & employment, window=4, required=3)

    base_d = (
        distance.lt(-20.0)
        & slope.lt(0.0)
        & family["risk_off_family_count"].ge(2)
    )
    candidate_d = _persistence(base_d, window=8, required=6)

    candidates = pd.DataFrame(
        {
            "CURRENT": current,
            "A": candidate_a,
            "B": candidate_b,
            "C": candidate_c,
            "D": candidate_d,
        },
        index=cycle.index,
    ).fillna(False)

    return candidates, family


def _weekly_recession_mask(index: pd.DatetimeIndex, episodes: list[RecessionEpisode]) -> pd.Series:
    mask = pd.Series(False, index=index, dtype=bool)
    for episode in episodes:
        mask.loc[(mask.index >= episode.start) & (mask.index <= episode.end)] = True
    return mask


def _onsets(series: pd.Series) -> pd.DatetimeIndex:
    active = series.fillna(False).astype(bool)
    onset = active & ~active.shift(1, fill_value=False)
    return pd.DatetimeIndex(series.index[onset])


def _nearest_onset(
    onsets: pd.DatetimeIndex,
    start: pd.Timestamp,
    *,
    before_weeks: int = 52,
    after_weeks: int = 26,
) -> pd.Timestamp | None:
    if len(onsets) == 0:
        return None
    left = pd.Timestamp(start) - pd.Timedelta(weeks=int(before_weeks))
    right = pd.Timestamp(start) + pd.Timedelta(weeks=int(after_weeks))
    nearby = onsets[(onsets >= left) & (onsets <= right)]
    if len(nearby) == 0:
        return None
    distances = np.abs((nearby - pd.Timestamp(start)).days)
    return pd.Timestamp(nearby[int(np.argmin(distances))])


def _weeks(delta: pd.Timedelta) -> float:
    return float(delta.total_seconds() / (7.0 * 24.0 * 3600.0))


def _spell_lengths(series: pd.Series) -> list[int]:
    active = series.fillna(False).astype(bool)
    lengths = []
    current = 0
    for value in active.tolist():
        if value:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def _episode_metrics(series: pd.Series, episodes: list[RecessionEpisode]) -> list[dict[str, Any]]:
    onsets = _onsets(series)
    rows = []
    for episode in episodes:
        nearest = _nearest_onset(onsets, episode.start)
        lag = _weeks(nearest - episode.start) if nearest is not None else None
        during = series.loc[(series.index >= episode.start) & (series.index <= episode.end)]
        rows.append(
            {
                "episode": episode.label,
                "start": episode.start.date().isoformat(),
                "end": episode.end.date().isoformat(),
                "onset": nearest.date().isoformat() if nearest is not None else None,
                "lag_weeks": lag,
                "hit_pm13w": bool(lag is not None and -13.0 <= lag <= 13.0),
                "overlap_share": float(during.astype(bool).mean()) if not during.empty else None,
                "shock_case": episode.start.year == 2020,
            }
        )
    return rows


def _aggregate(
    *,
    series: pd.Series,
    episode_rows: list[dict[str, Any]],
    episodes: list[RecessionEpisode],
    exclude_shock: bool,
) -> dict[str, Any]:
    selected = [row for row in episode_rows if not exclude_shock or not row["shock_case"]]
    selected_episodes = [
        episode for episode in episodes
        if not exclude_shock or episode.start.year != 2020
    ]

    lags = [
        float(row["lag_weeks"])
        for row in selected
        if row["lag_weeks"] is not None and np.isfinite(float(row["lag_weeks"]))
    ]
    overlaps = [
        float(row["overlap_share"])
        for row in selected
        if row["overlap_share"] is not None and np.isfinite(float(row["overlap_share"]))
    ]
    hits = sum(bool(row["hit_pm13w"]) for row in selected)

    recession_mask = _weekly_recession_mask(series.index, selected_episodes)
    outside = ~recession_mask
    false_share = float(series.loc[outside].astype(bool).mean()) if outside.any() else None
    spells = _spell_lengths(series)

    return {
        "episodes": len(selected),
        "hit_pm13w_rate": hits / len(selected) if selected else None,
        "median_lag_weeks": float(np.median(lags)) if lags else None,
        "mean_overlap_share": float(np.mean(overlaps)) if overlaps else None,
        "false_contraction_share": false_share,
        "average_active_spell_weeks": float(np.mean(spells)) if spells else None,
    }


def _current_onset(series: pd.Series) -> pd.Timestamp | None:
    active = series.fillna(False).astype(bool)
    if active.empty or not bool(active.iloc[-1]):
        return None
    values = active.tolist()
    pos = len(values) - 1
    while pos > 0 and values[pos - 1]:
        pos -= 1
    return pd.Timestamp(active.index[pos])


def evaluate_contraction_candidates(
    *,
    cycle_history: pd.DataFrame,
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
    usrec_frame: pd.DataFrame,
    start_year: int = 1990,
) -> dict[str, Any]:
    """Research-only comparison. Results never change production cycle phase."""
    candidates, _ = build_candidate_series(
        cycle_history=cycle_history,
        weekly_scores=weekly_scores,
        features=features,
        config=config,
    )
    episodes = recession_episodes_from_usrec(usrec_frame, start_year=start_year)

    if candidates.empty:
        return {
            "mode": "RESEARCH_ONLY_NO_AUTO_CALIBRATION",
            "candidates": [],
            "episodes": [],
            "warning": "No candidate history available.",
        }

    candidate_rows = []
    episode_rows = []

    for key, meta in CANDIDATES.items():
        series = candidates[key].astype(bool)
        per_episode = _episode_metrics(series, episodes)
        for row in per_episode:
            episode_rows.append(
                {"candidate": key, "candidate_label": meta["label"], **row}
            )

        normal = _aggregate(
            series=series,
            episode_rows=per_episode,
            episodes=episodes,
            exclude_shock=True,
        )
        all_episodes = _aggregate(
            series=series,
            episode_rows=per_episode,
            episodes=episodes,
            exclude_shock=False,
        )
        onset = _current_onset(series)

        candidate_rows.append(
            {
                "candidate": key,
                "label": meta["label"],
                "logic": meta["logic"],
                "current_active": bool(series.iloc[-1]),
                "current_onset": onset.date().isoformat() if onset is not None else None,
                "normal_hit_pm13w_rate": normal["hit_pm13w_rate"],
                "normal_median_lag_weeks": normal["median_lag_weeks"],
                "normal_mean_overlap_share": normal["mean_overlap_share"],
                "normal_false_contraction_share": normal["false_contraction_share"],
                "normal_avg_spell_weeks": normal["average_active_spell_weeks"],
                "all_hit_pm13w_rate": all_episodes["hit_pm13w_rate"],
                "all_median_lag_weeks": all_episodes["median_lag_weeks"],
                "all_mean_overlap_share": all_episodes["mean_overlap_share"],
                "all_false_contraction_share": all_episodes["false_contraction_share"],
            }
        )

    return {
        "mode": "RESEARCH_ONLY_NO_AUTO_CALIBRATION",
        "as_of": candidates.index.max().date().isoformat() if len(candidates.index) else None,
        "candidates": candidate_rows,
        "episodes": episode_rows,
        "normal_cycle_definition": (
            "1990/91, 2001 and 2008/09 are summarized as normal-cycle episodes. "
            "2020 remains visible but is separated as an exogenous shock case."
        ),
        "warning": (
            "Candidate results are retrospective diagnostics on current/revised FRED history. "
            "They do not change the production Cycle Phase, do not select a winner automatically, "
            "and are not a true point-in-time calibration until vintage data is available."
        ),
    }
