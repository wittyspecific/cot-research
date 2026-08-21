from __future__ import annotations

from math import comb, sqrt
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .yield_cot_regime_event_study import (
    run_regime_aware_event_study,
)


# V3.19.2 · STRICT RETROSPECTIVE OOS CONFLICT VALIDATION
#
# FROZEN hypotheses from V3.19.1:
#
# H1:
#   COT Stage = ACTIVE
#   20D Rates = STRONG / EXTREME
#   COT vs Rates = CONFLICT
#   Direction evaluated = Rates
#   Horizon = 8W
#
# H2:
#   COT Stage = EARLY
#   20D Rates = STRONG / EXTREME
#   COT vs Rates = CONFLICT
#   Direction evaluated = Rates
#   Horizon = 8W
#
# H3 (secondary):
#   COT Stage = ACTIVE
#   20D Rates = EXTREME
#   COT vs Rates = ALIGNED
#   Direction evaluated = COT
#   Horizon = 4W
#
# No thresholds are searched or optimized here.
# No COT logic is defined or changed here.
#
# IMPORTANT statistical limitation:
# These hypotheses were discovered while inspecting the same historical
# universe. Therefore this is a strict retrospective robustness / pseudo-OOS
# validation, NOT a pristine untouched holdout. Final confirmation requires
# future observations after the hypothesis freeze date.

FREEZE_DATE_V3192 = pd.Timestamp("2026-08-21")
MIN_N_ROBUST_V3192 = 40
BOOTSTRAP_REPS_V3192 = 3000
RNG_SEED_V3192 = 3192


def _finite_v3192(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _wilson_v3192(
    wins: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total <= 0:
        return np.nan, np.nan
    p = float(wins) / float(total)
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    half = (
        z
        * sqrt(
            (
                p * (1.0 - p)
                + z2 / (4.0 * total)
            )
            / total
        )
        / denom
    )
    return (
        max(0.0, center - half),
        min(1.0, center + half),
    )


def _binomial_two_sided_v3192(
    wins: int,
    total: int,
    p0: float = 0.5,
) -> float:
    """Exact two-sided binomial p-value, no scipy dependency."""
    if total <= 0:
        return np.nan

    probs = np.asarray(
        [
            comb(total, k)
            * (p0 ** k)
            * ((1.0 - p0) ** (total - k))
            for k in range(total + 1)
        ],
        dtype=float,
    )
    observed = probs[int(wins)]
    pvalue = float(
        probs[
            probs <= observed + 1e-15
        ].sum()
    )
    return min(1.0, pvalue)


def _deoverlap_v3192(
    frame: pd.DataFrame,
    *,
    horizon_weeks: int,
) -> pd.DataFrame:
    """Keep non-overlapping observations within each FX pair."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    kept = []
    gap = pd.Timedelta(weeks=int(horizon_weeks))

    for _, group in (
        frame.sort_values(
            ["pair", "available_date"]
        )
        .groupby("pair", sort=False)
    ):
        next_allowed = None
        for idx, row in group.iterrows():
            date = pd.Timestamp(row["available_date"])
            if next_allowed is None or date >= next_allowed:
                kept.append(idx)
                next_allowed = date + gap

    return (
        frame.loc[kept]
        .sort_values(
            ["available_date", "pair"]
        )
        .reset_index(drop=True)
    )


def _oriented_returns_v3192(
    frame: pd.DataFrame,
    *,
    return_col: str,
    direction_col: str,
) -> pd.Series:
    raw = pd.to_numeric(
        frame[return_col],
        errors="coerce",
    )
    direction = pd.to_numeric(
        frame[direction_col],
        errors="coerce",
    )
    out = raw * direction
    return out[
        np.isfinite(out)
    ]


def _cluster_bootstrap_mean_v3192(
    frame: pd.DataFrame,
    *,
    return_col: str,
    direction_col: str,
    cluster_col: str,
) -> tuple[float, float]:
    clean = frame.copy()
    clean["_oriented"] = (
        pd.to_numeric(
            clean[return_col],
            errors="coerce",
        )
        * pd.to_numeric(
            clean[direction_col],
            errors="coerce",
        )
    )
    clean = clean[
        np.isfinite(clean["_oriented"])
    ].copy()

    clusters = [
        group["_oriented"].to_numpy(dtype=float)
        for _, group in clean.groupby(cluster_col)
        if not group.empty
    ]
    if len(clusters) < 2:
        return np.nan, np.nan

    rng = np.random.default_rng(RNG_SEED_V3192)
    means = np.empty(
        BOOTSTRAP_REPS_V3192,
        dtype=float,
    )

    for i in range(BOOTSTRAP_REPS_V3192):
        selected = rng.integers(
            0,
            len(clusters),
            size=len(clusters),
        )
        sample = np.concatenate(
            [
                clusters[j]
                for j in selected
            ]
        )
        means[i] = float(
            np.mean(sample)
        )

    return (
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def _positive_share_v3192(
    frame: pd.DataFrame,
    *,
    return_col: str,
    direction_col: str,
    group_col: str,
) -> tuple[int, int, float]:
    rows = []

    for group, subset in frame.groupby(group_col):
        oriented = _oriented_returns_v3192(
            subset,
            return_col=return_col,
            direction_col=direction_col,
        )
        if oriented.empty:
            continue
        rows.append(
            (
                group,
                float(oriented.mean()),
            )
        )

    if not rows:
        return 0, 0, np.nan

    positive = sum(
        mean > 0
        for _, mean in rows
    )
    total = len(rows)
    return (
        int(positive),
        int(total),
        float(positive / total),
    )


def _status_v3192(
    *,
    n: int,
    hit_rate: float,
    hit_ci_low: float,
    median_return: float,
    mean_return: float,
    pair_boot_low: float,
    year_positive_share: float,
) -> str:
    robust = (
        n >= MIN_N_ROBUST_V3192
        and np.isfinite(hit_ci_low)
        and hit_ci_low > 0.50
        and np.isfinite(median_return)
        and median_return > 0
        and np.isfinite(mean_return)
        and mean_return > 0
        and np.isfinite(pair_boot_low)
        and pair_boot_low > 0
        and np.isfinite(year_positive_share)
        and year_positive_share >= 0.60
    )
    if robust:
        return "ROBUST RETROSPECTIVE"

    promising = (
        n >= 30
        and np.isfinite(hit_rate)
        and hit_rate >= 0.55
        and np.isfinite(median_return)
        and median_return > 0
        and np.isfinite(mean_return)
        and mean_return > 0
    )
    if promising:
        return "PROMISING · NOT CONFIRMED"

    return "NOT CONFIRMED"


def _evaluate_hypothesis_v3192(
    events: pd.DataFrame,
    *,
    hypothesis: str,
    stage: str,
    strength_values: set[str],
    relationship: str,
    direction_col: str,
    horizon_weeks: int,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    return_col = f"return_{int(horizon_weeks)}w"

    subset = events[
        events["cot_stage"].eq(stage)
        & events[
            "rates_strength"
        ].isin(strength_values)
        & events[
            "relationship"
        ].eq(relationship)
    ].copy()

    subset = subset.dropna(
        subset=[
            "available_date",
            return_col,
            direction_col,
        ]
    )
    subset = _deoverlap_v3192(
        subset,
        horizon_weeks=horizon_weeks,
    )

    oriented = _oriented_returns_v3192(
        subset,
        return_col=return_col,
        direction_col=direction_col,
    )

    if oriented.empty:
        summary = {
            "Hypothese": hypothesis,
            "Status": "INSUFFICIENT DATA",
            "n": 0,
            "Hit Rate": np.nan,
            "Hit CI Low": np.nan,
            "Hit CI High": np.nan,
            "Binomial p": np.nan,
            "Median Return": np.nan,
            "Mean Return": np.nan,
            "Pair Bootstrap Low": np.nan,
            "Pair Bootstrap High": np.nan,
            "Year + Share": np.nan,
            "Pair + Share": np.nan,
        }
        return (
            summary,
            pd.DataFrame(),
            pd.DataFrame(),
        )

    wins = int(
        (oriented > 0).sum()
    )
    n = int(
        len(oriented)
    )
    hit_rate = float(
        wins / n
    )
    ci_low, ci_high = _wilson_v3192(
        wins,
        n,
    )
    binomial_p = _binomial_two_sided_v3192(
        wins,
        n,
        0.5,
    )

    pair_boot_low, pair_boot_high = (
        _cluster_bootstrap_mean_v3192(
            subset,
            return_col=return_col,
            direction_col=direction_col,
            cluster_col="pair",
        )
    )

    year_subset = subset.copy()
    year_subset["year"] = pd.to_datetime(
        year_subset["available_date"]
    ).dt.year.astype(int)

    year_pos, year_total, year_share = (
        _positive_share_v3192(
            year_subset,
            return_col=return_col,
            direction_col=direction_col,
            group_col="year",
        )
    )
    pair_pos, pair_total, pair_share = (
        _positive_share_v3192(
            subset,
            return_col=return_col,
            direction_col=direction_col,
            group_col="pair",
        )
    )

    median_return = float(
        oriented.median()
    )
    mean_return = float(
        oriented.mean()
    )

    status = _status_v3192(
        n=n,
        hit_rate=hit_rate,
        hit_ci_low=ci_low,
        median_return=median_return,
        mean_return=mean_return,
        pair_boot_low=pair_boot_low,
        year_positive_share=year_share,
    )

    summary = {
        "Hypothese": hypothesis,
        "Status": status,
        "n": n,
        "Hit Rate": hit_rate,
        "Hit CI Low": ci_low,
        "Hit CI High": ci_high,
        "Binomial p": binomial_p,
        "Median Return": median_return,
        "Mean Return": mean_return,
        "Pair Bootstrap Low": pair_boot_low,
        "Pair Bootstrap High": pair_boot_high,
        "Positive Years": year_pos,
        "Years": year_total,
        "Year + Share": year_share,
        "Positive Pairs": pair_pos,
        "Pairs": pair_total,
        "Pair + Share": pair_share,
    }

    yearly_rows = []
    for year, group in year_subset.groupby("year"):
        values = _oriented_returns_v3192(
            group,
            return_col=return_col,
            direction_col=direction_col,
        )
        if values.empty:
            continue
        yearly_rows.append(
            {
                "Hypothese": hypothesis,
                "Jahr": int(year),
                "n": int(len(values)),
                "Hit Rate": float(
                    (values > 0).mean()
                ),
                "Median Return": float(
                    values.median()
                ),
                "Mean Return": float(
                    values.mean()
                ),
            }
        )

    pair_rows = []
    for pair, group in subset.groupby("pair"):
        values = _oriented_returns_v3192(
            group,
            return_col=return_col,
            direction_col=direction_col,
        )
        if values.empty:
            continue
        pair_rows.append(
            {
                "Hypothese": hypothesis,
                "Paar": str(pair),
                "n": int(len(values)),
                "Hit Rate": float(
                    (values > 0).mean()
                ),
                "Median Return": float(
                    values.median()
                ),
                "Mean Return": float(
                    values.mean()
                ),
            }
        )

    return (
        summary,
        pd.DataFrame(yearly_rows),
        pd.DataFrame(pair_rows),
    )



# V3.19.2 · RUNTIME V3191 SCHEMA NORMALIZER V2
def _normalize_v3191_event_schema_v3192(
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Compatibility adapter only. No COT state is calculated or changed."""
    if events is None or events.empty:
        return pd.DataFrame()

    out = events.copy()

    aliases = {
        "cot_stage": ("cot_stage", "cot_stage_v3191"),
        "rates_strength": ("rates_strength", "rates_strength_v3191"),
        "relationship": ("relationship", "relationship_v3191"),
        "rates20_raw_direction": (
            "rates20_raw_direction",
            "rates20_raw_direction_v3191",
        ),
    }

    missing = []
    for canonical, candidates in aliases.items():
        if canonical in out.columns:
            continue

        source = next(
            (
                candidate
                for candidate in candidates
                if candidate in out.columns
            ),
            None,
        )

        if source is None:
            missing.append(canonical)
        else:
            out[canonical] = out[source]

    if missing:
        raise KeyError(
            "V3.19.2 Event-Schema inkompatibel. Fehlend: "
            + ", ".join(missing)
            + ". Vorhandene Spalten: "
            + ", ".join(map(str, out.columns))
        )

    return out


def run_strict_conflict_validation_v3192(
    v3190_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen H1/H2/H3 rules with no parameter search."""
    v3191 = run_regime_aware_event_study(
        v3190_result
    )
    events = pd.DataFrame(
        v3191.get(
            "events",
            pd.DataFrame(),
        )
    )
    events = _normalize_v3191_event_schema_v3192(events)

    if events.empty:
        return {
            "summary": pd.DataFrame(),
            "by_year": pd.DataFrame(),
            "by_pair": pd.DataFrame(),
            "meta": {
                "freeze_date": FREEZE_DATE_V3192,
                "note": (
                    "Keine V3.19.1 Events verfügbar."
                ),
            },
        }

    specs = [
        {
            "hypothesis": (
                "H1 · ACTIVE Conflict → Rates · 8W"
            ),
            "stage": "ACTIVE",
            "strength_values": {
                "STRONG",
                "EXTREME",
            },
            "relationship": "CONFLICT",
            "direction_col": (
                "rates20_raw_direction"
            ),
            "horizon_weeks": 8,
        },
        {
            "hypothesis": (
                "H2 · EARLY Conflict → Rates · 8W"
            ),
            "stage": "EARLY",
            "strength_values": {
                "STRONG",
                "EXTREME",
            },
            "relationship": "CONFLICT",
            "direction_col": (
                "rates20_raw_direction"
            ),
            "horizon_weeks": 8,
        },
        {
            "hypothesis": (
                "H3 · ACTIVE EXTREME Aligned → COT · 4W"
            ),
            "stage": "ACTIVE",
            "strength_values": {
                "EXTREME",
            },
            "relationship": "ALIGNED",
            "direction_col": (
                "cot_pair_direction"
            ),
            "horizon_weeks": 4,
        },
    ]

    summaries = []
    years = []
    pairs = []

    for spec in specs:
        summary, by_year, by_pair = (
            _evaluate_hypothesis_v3192(
                events,
                **spec,
            )
        )
        summaries.append(summary)
        if not by_year.empty:
            years.append(by_year)
        if not by_pair.empty:
            pairs.append(by_pair)

    return {
        "summary": pd.DataFrame(
            summaries
        ),
        "by_year": (
            pd.concat(
                years,
                ignore_index=True,
            )
            if years
            else pd.DataFrame()
        ),
        "by_pair": (
            pd.concat(
                pairs,
                ignore_index=True,
            )
            if pairs
            else pd.DataFrame()
        ),
        "meta": {
            "freeze_date": FREEZE_DATE_V3192,
            "bootstrap_reps": (
                BOOTSTRAP_REPS_V3192
            ),
            "non_overlap": (
                "8W H1/H2; 4W H3 per FX pair"
            ),
            "interpretation": (
                "Retrospective robustness / pseudo-OOS only. "
                "Not pristine unseen OOS because hypotheses were "
                "discovered on the same historical universe."
            ),
        },
    }


__all__ = [
    "run_strict_conflict_validation_v3192",
    "_deoverlap_v3192",
    "_binomial_two_sided_v3192",
    "FREEZE_DATE_V3192",
]
