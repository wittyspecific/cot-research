from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.positioning_robustness import add_research_time_split


CANDIDATE_KEY_COLUMNS = (
    "candidate_type",
    "window_weeks",
    "threshold_upper",
    "threshold_lower",
    "feature",
    "flow_quantile",
    "horizon_weeks",
)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_candidate_key(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["candidate_type"] = out["candidate_type"].astype(str)
    out["feature"] = out["feature"].astype(str)
    for col in (
        "window_weeks",
        "threshold_upper",
        "threshold_lower",
        "flow_quantile",
        "horizon_weeks",
    ):
        out[col] = _numeric(out[col])
    return out


def aggregate_cross_market_scans(
    scans_by_market: Mapping[str, pd.DataFrame],
    *,
    min_markets: int = 4,
) -> pd.DataFrame:
    """Aggregate identical Train/Validation candidate definitions across markets.

    The ranking deliberately ignores every OOS column. Flow cutoffs remain
    market-specific because each single-market scanner estimated them from that
    market's TRAIN segment only.

    The result therefore asks whether the *same research definition* (e.g.
    156W, 80/20, Net/OI Velocity 2W, Top 25%) behaves consistently across
    multiple currency markets without forcing a common absolute flow cutoff.
    """
    frames = []
    supplied_markets = []

    for market_name, scan in scans_by_market.items():
        if scan is None or scan.empty:
            continue
        work = _normalize_candidate_key(scan)
        if "sample_ok" not in work.columns:
            continue
        work = work[work["sample_ok"].fillna(False)].copy()
        if work.empty:
            continue

        work["market_name"] = str(market_name)
        frames.append(work)
        supplied_markets.append(str(market_name))

    if not frames:
        return pd.DataFrame()

    pooled = pd.concat(frames, ignore_index=True)
    total_markets = len(set(supplied_markets))
    rows = []

    for keys, subset in pooled.groupby(
        list(CANDIDATE_KEY_COLUMNS),
        dropna=False,
    ):
        key = dict(zip(CANDIDATE_KEY_COLUMNS, keys))

        val = _numeric(subset["validation_median"])
        train = _numeric(subset["train_median"])
        val_hit = _numeric(subset["validation_hit_rate"])
        robust = _numeric(subset["robustness_score"])
        neighborhood = _numeric(subset["neighbor_positive_share"])
        n_val = _numeric(subset["n_validation"])

        market_valid = val.notna()
        markets_eligible = int(market_valid.sum())
        if markets_eligible == 0:
            continue

        positive_validation = val[market_valid] > 0
        both_positive = (
            train[market_valid].gt(0)
            & val[market_valid].gt(0)
        )

        coverage = (
            markets_eligible / total_markets
            if total_markets
            else np.nan
        )
        positive_share = float(positive_validation.mean())
        replicated_share = float(both_positive.mean())
        median_validation = float(val[market_valid].median())
        median_hit = (
            float(val_hit[market_valid].median())
            if val_hit[market_valid].notna().any()
            else np.nan
        )
        median_robustness = (
            float(robust[market_valid].median())
            if robust[market_valid].notna().any()
            else np.nan
        )
        median_neighbor = (
            float(neighborhood[market_valid].median())
            if neighborhood[market_valid].notna().any()
            else np.nan
        )
        median_n_validation = (
            float(n_val[market_valid].median())
            if n_val[market_valid].notna().any()
            else 0.0
        )

        # Cross-market score intentionally rewards breadth and replication,
        # not the largest absolute historical return.
        coverage_component = 20.0 * float(np.clip(coverage, 0.0, 1.0))
        validation_component = 35.0 * float(np.clip(positive_share, 0.0, 1.0))
        replication_component = 20.0 * float(np.clip(replicated_share, 0.0, 1.0))
        robustness_component = 15.0 * float(
            np.clip(
                0.0 if not np.isfinite(median_robustness)
                else median_robustness / 100.0,
                0.0,
                1.0,
            )
        )
        sample_component = 10.0 * float(
            np.clip(median_n_validation / 6.0, 0.0, 1.0)
        )

        score = (
            coverage_component
            + validation_component
            + replication_component
            + robustness_component
            + sample_component
        )

        if (
            markets_eligible >= max(5, int(min_markets))
            and positive_share >= 0.70
            and replicated_share >= 0.65
            and score >= 75
        ):
            status = "CROSS-MARKET ROBUST"
        elif (
            markets_eligible >= int(min_markets)
            and positive_share >= 0.60
            and score >= 62
        ):
            status = "PROMISING ACROSS MARKETS"
        elif markets_eligible >= int(min_markets) and positive_share >= 0.50:
            status = "MIXED"
        else:
            status = "WEAK / MARKET-SPECIFIC"

        row = {
            **key,
            "markets_total": int(total_markets),
            "markets_eligible": markets_eligible,
            "market_coverage": float(coverage),
            "positive_validation_markets": int(positive_validation.sum()),
            "positive_validation_share": positive_share,
            "train_validation_positive_markets": int(both_positive.sum()),
            "train_validation_positive_share": replicated_share,
            "median_validation_return": median_validation,
            "median_validation_hit_rate": median_hit,
            "median_single_market_robustness": median_robustness,
            "median_neighbor_positive_share": median_neighbor,
            "median_n_validation": median_n_validation,
            "total_n_validation": int(n_val[market_valid].fillna(0).sum()),
            "cross_market_score": float(np.clip(score, 0.0, 100.0)),
            "cross_market_status": status,
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    eligible = out["markets_eligible"].ge(int(min_markets))
    out["cross_market_rank"] = np.nan

    if eligible.any():
        ranked = (
            out.loc[eligible]
            .sort_values(
                [
                    "cross_market_score",
                    "positive_validation_share",
                    "markets_eligible",
                    "median_single_market_robustness",
                ],
                ascending=[False, False, False, False],
            )
            .index
        )
        out.loc[ranked, "cross_market_rank"] = np.arange(
            1,
            len(ranked) + 1,
        )

    return out.sort_values(
        [
            "markets_eligible",
            "cross_market_score",
            "positive_validation_share",
        ],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def cross_market_candidate_detail(
    scans_by_market: Mapping[str, pd.DataFrame],
    candidate,
) -> pd.DataFrame:
    """Return Train/Validation detail for one cross-market candidate.

    OOS is intentionally omitted from the returned table.
    """
    if not scans_by_market:
        return pd.DataFrame()

    candidate = pd.Series(candidate)
    rows = []

    for market_name, scan in scans_by_market.items():
        if scan is None or scan.empty:
            continue

        work = _normalize_candidate_key(scan)
        mask = pd.Series(True, index=work.index)

        for col in CANDIDATE_KEY_COLUMNS:
            if col not in work.columns:
                mask &= False
                continue

            target = candidate.get(col)
            if col in ("candidate_type", "feature"):
                mask &= work[col].astype(str).eq(str(target))
            else:
                values = _numeric(work[col])
                if pd.isna(target):
                    mask &= values.isna()
                else:
                    mask &= values.eq(float(target))

        matches = work.loc[mask].copy()
        if matches.empty:
            continue

        chosen = matches.sort_values(
            ["rank_train_validation", "robustness_score"],
            ascending=[True, False],
        ).iloc[0]

        rows.append(
            {
                "market_name": str(market_name),
                "sample_ok": bool(chosen.get("sample_ok", False)),
                "n_train": int(chosen.get("n_train", 0) or 0),
                "train_median": float(chosen.get("train_median", np.nan)),
                "train_hit_rate": float(chosen.get("train_hit_rate", np.nan)),
                "n_validation": int(chosen.get("n_validation", 0) or 0),
                "validation_median": float(
                    chosen.get("validation_median", np.nan)
                ),
                "validation_hit_rate": float(
                    chosen.get("validation_hit_rate", np.nan)
                ),
                "neighbor_positive_share": float(
                    chosen.get("neighbor_positive_share", np.nan)
                ),
                "robustness_score": float(
                    chosen.get("robustness_score", np.nan)
                ),
                "status": str(chosen.get("status", "")),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        ["validation_median", "robustness_score"],
        ascending=[False, False],
    ).reset_index(drop=True)


def cross_market_findings(scan: pd.DataFrame) -> dict:
    if scan is None or scan.empty:
        return {
            "top_state": None,
            "top_flow": None,
            "robust_count": 0,
            "promising_count": 0,
        }

    eligible = scan[scan["cross_market_rank"].notna()].copy()
    state = eligible[eligible["candidate_type"].eq("STATE")]
    flow = eligible[eligible["candidate_type"].eq("FLOW")]

    return {
        "top_state": (
            state.sort_values("cross_market_rank").iloc[0].to_dict()
            if not state.empty
            else None
        ),
        "top_flow": (
            flow.sort_values("cross_market_rank").iloc[0].to_dict()
            if not flow.empty
            else None
        ),
        "robust_count": int(
            (eligible["cross_market_status"] == "CROSS-MARKET ROBUST").sum()
        ),
        "promising_count": int(
            (
                eligible["cross_market_status"]
                == "PROMISING ACROSS MARKETS"
            ).sum()
        ),
    }

def _candidate_match_mask(frame: pd.DataFrame, candidate) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)

    row = pd.Series(candidate)
    mask = pd.Series(True, index=frame.index)

    for col in CANDIDATE_KEY_COLUMNS:
        if col not in frame.columns:
            return pd.Series(False, index=frame.index)

        target = row.get(col)
        if col in ("candidate_type", "feature"):
            mask &= frame[col].astype(str).eq(str(target))
        else:
            values = pd.to_numeric(frame[col], errors="coerce")
            if pd.isna(target):
                mask &= values.isna()
            else:
                mask &= np.isclose(
                    values.to_numpy(dtype=float),
                    float(target),
                    equal_nan=False,
                )

    return mask


def cross_market_coverage_diagnostic(
    cross_scan: pd.DataFrame,
) -> pd.DataFrame:
    """Make eligible-vs-total market coverage explicit.

    This prevents e.g. 4/5 positive eligible markets from being read as if
    80% of a seven-market universe had actually produced positive evidence.
    """
    if cross_scan is None or cross_scan.empty:
        return pd.DataFrame()

    out = cross_scan.copy()
    total = pd.to_numeric(out["markets_total"], errors="coerce")
    eligible = pd.to_numeric(out["markets_eligible"], errors="coerce")
    positive = pd.to_numeric(
        out["positive_validation_markets"],
        errors="coerce",
    )

    out["markets_insufficient"] = (total - eligible).clip(lower=0)
    out["positive_of_total_share"] = np.where(
        total > 0,
        positive / total,
        np.nan,
    )
    out["eligible_of_total_share"] = np.where(
        total > 0,
        eligible / total,
        np.nan,
    )
    out["coverage_text"] = out.apply(
        lambda r: (
            f"{int(r['positive_validation_markets'])} positiv / "
            f"{int(r['markets_eligible'])} eligible / "
            f"{int(r['markets_total'])} total"
        ),
        axis=1,
    )
    return out


def cross_market_leave_one_out(
    scans_by_market: Mapping[str, pd.DataFrame],
    candidate,
    *,
    min_markets: int = 3,
) -> pd.DataFrame:
    """Recompute the candidate after omitting each market once.

    OOS remains irrelevant because aggregate_cross_market_scans itself uses
    Train/Validation columns only.
    """
    if not scans_by_market:
        return pd.DataFrame()

    full = aggregate_cross_market_scans(
        scans_by_market,
        min_markets=int(min_markets),
    )
    if full.empty:
        return pd.DataFrame()

    full_match = full.loc[_candidate_match_mask(full, candidate)]
    if full_match.empty:
        return pd.DataFrame()

    full_row = full_match.iloc[0]
    full_score = float(full_row.get("cross_market_score", np.nan))
    rows = []

    for omitted in sorted(scans_by_market):
        reduced = {
            name: scan
            for name, scan in scans_by_market.items()
            if name != omitted
        }
        reduced_scan = aggregate_cross_market_scans(
            reduced,
            min_markets=min(
                int(min_markets),
                max(1, len(reduced)),
            ),
        )

        match = (
            reduced_scan.loc[
                _candidate_match_mask(reduced_scan, candidate)
            ]
            if not reduced_scan.empty
            else pd.DataFrame()
        )

        if match.empty:
            rows.append(
                {
                    "omitted_market": omitted,
                    "markets_eligible": 0,
                    "positive_validation_share": np.nan,
                    "train_validation_positive_share": np.nan,
                    "cross_market_score": np.nan,
                    "score_delta": np.nan,
                    "cross_market_status": "NO COMMON CANDIDATE",
                }
            )
            continue

        row = match.iloc[0]
        score = float(row.get("cross_market_score", np.nan))
        rows.append(
            {
                "omitted_market": omitted,
                "markets_eligible": int(
                    row.get("markets_eligible", 0) or 0
                ),
                "positive_validation_share": float(
                    row.get("positive_validation_share", np.nan)
                ),
                "train_validation_positive_share": float(
                    row.get(
                        "train_validation_positive_share",
                        np.nan,
                    )
                ),
                "cross_market_score": score,
                "score_delta": (
                    score - full_score
                    if np.isfinite(score) and np.isfinite(full_score)
                    else np.nan
                ),
                "cross_market_status": str(
                    row.get("cross_market_status", "")
                ),
            }
        )

    return pd.DataFrame(rows)


def leave_one_out_summary(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {
            "worst_score": np.nan,
            "max_abs_delta": np.nan,
            "positive_share_min": np.nan,
            "stable": False,
        }

    score = pd.to_numeric(
        table["cross_market_score"],
        errors="coerce",
    )
    delta = pd.to_numeric(table["score_delta"], errors="coerce")
    positive = pd.to_numeric(
        table["positive_validation_share"],
        errors="coerce",
    )

    worst_score = (
        float(score.min())
        if score.notna().any()
        else np.nan
    )
    max_abs_delta = (
        float(delta.abs().max())
        if delta.notna().any()
        else np.nan
    )
    positive_min = (
        float(positive.min())
        if positive.notna().any()
        else np.nan
    )

    stable = bool(
        np.isfinite(worst_score)
        and np.isfinite(max_abs_delta)
        and np.isfinite(positive_min)
        and worst_score >= 62.0
        and max_abs_delta <= 12.0
        and positive_min >= 0.60
    )

    return {
        "worst_score": worst_score,
        "max_abs_delta": max_abs_delta,
        "positive_share_min": positive_min,
        "stable": stable,
    }


def _candidate_event_dates(
    events: pd.DataFrame,
    market_scan: pd.DataFrame,
    candidate,
) -> set[pd.Timestamp]:
    """Train+Validation event dates selected by one FLOW candidate."""
    if events is None or events.empty:
        return set()
    if market_scan is None or market_scan.empty:
        return set()

    candidate = pd.Series(candidate)
    if str(candidate.get("candidate_type", "")) != "FLOW":
        return set()

    match = market_scan.loc[
        _candidate_match_mask(market_scan, candidate)
    ]
    if match.empty:
        return set()

    market_row = match.sort_values(
        ["rank_train_validation", "robustness_score"],
        ascending=[True, False],
    ).iloc[0]

    feature = str(candidate.get("feature", ""))
    cutoff = pd.to_numeric(
        pd.Series([market_row.get("flow_cutoff_train")]),
        errors="coerce",
    ).iloc[0]

    if feature not in events.columns or not np.isfinite(cutoff):
        return set()

    work = events.copy()
    if "release_available" in work.columns:
        work = work[work["release_available"].fillna(False)].copy()

    work = work.dropna(
        subset=[
            "release_report_date",
            "window_weeks",
            "threshold_upper",
            "threshold_lower",
        ]
    )
    if work.empty:
        return set()

    split, meta = add_research_time_split(
        work,
        train_share=0.60,
        validation_share=0.20,
    )
    if split.empty or not meta.get("enough_history", False):
        return set()

    mask = (
        pd.to_numeric(
            split["window_weeks"],
            errors="coerce",
        ).eq(float(candidate["window_weeks"]))
        & np.isclose(
            pd.to_numeric(
                split["threshold_upper"],
                errors="coerce",
            ).to_numpy(dtype=float),
            float(candidate["threshold_upper"]),
            equal_nan=False,
        )
        & np.isclose(
            pd.to_numeric(
                split["threshold_lower"],
                errors="coerce",
            ).to_numpy(dtype=float),
            float(candidate["threshold_lower"]),
            equal_nan=False,
        )
        & split["research_split"].isin(["TRAIN", "VALIDATION"])
        & (
            pd.to_numeric(split[feature], errors="coerce")
            >= float(cutoff)
        )
    )

    dates = pd.to_datetime(
        split.loc[mask, "release_report_date"],
        errors="coerce",
    ).dropna()

    return set(dates.tolist())


def cross_market_flow_redundancy(
    events_by_market: Mapping[str, pd.DataFrame],
    scans_by_market: Mapping[str, pd.DataFrame],
    cross_scan: pd.DataFrame,
    *,
    top_n: int = 8,
    redundancy_threshold: float = 0.80,
) -> pd.DataFrame:
    """Pairwise Jaccard overlap for top cross-market FLOW hypotheses.

    Every market uses its own TRAIN-estimated cutoff. Only TRAIN+VALIDATION
    release events enter the overlap calculation; OOS dates are excluded.
    """
    if (
        cross_scan is None
        or cross_scan.empty
        or not events_by_market
        or not scans_by_market
    ):
        return pd.DataFrame()

    flow = cross_scan[
        cross_scan["candidate_type"].astype(str).eq("FLOW")
        & cross_scan["cross_market_rank"].notna()
    ].sort_values("cross_market_rank").head(int(top_n))

    if len(flow) < 2:
        return pd.DataFrame()

    rows = []
    indices = list(flow.index)

    for left_pos in range(len(indices)):
        for right_pos in range(left_pos + 1, len(indices)):
            left = flow.loc[indices[left_pos]]
            right = flow.loc[indices[right_pos]]
            market_rows = []

            common_markets = sorted(
                set(events_by_market)
                & set(scans_by_market)
            )

            for market_name in common_markets:
                left_dates = _candidate_event_dates(
                    events_by_market[market_name],
                    scans_by_market[market_name],
                    left,
                )
                right_dates = _candidate_event_dates(
                    events_by_market[market_name],
                    scans_by_market[market_name],
                    right,
                )

                union = left_dates | right_dates
                if not union:
                    continue

                intersection = left_dates & right_dates
                market_rows.append(
                    {
                        "market_name": market_name,
                        "jaccard": len(intersection) / len(union),
                        "n_left": len(left_dates),
                        "n_right": len(right_dates),
                        "n_union": len(union),
                    }
                )

            if not market_rows:
                continue

            detail = pd.DataFrame(market_rows)
            median_jaccard = float(detail["jaccard"].median())
            mean_jaccard = float(detail["jaccard"].mean())

            rows.append(
                {
                    "rank_a": int(left["cross_market_rank"]),
                    "rank_b": int(right["cross_market_rank"]),
                    "window_a": int(left["window_weeks"]),
                    "threshold_a": float(left["threshold_upper"]),
                    "feature_a": str(left["feature"]),
                    "flow_quantile_a": float(left["flow_quantile"]),
                    "window_b": int(right["window_weeks"]),
                    "threshold_b": float(right["threshold_upper"]),
                    "feature_b": str(right["feature"]),
                    "flow_quantile_b": float(right["flow_quantile"]),
                    "markets_compared": int(len(detail)),
                    "median_jaccard": median_jaccard,
                    "mean_jaccard": mean_jaccard,
                    "max_jaccard": float(detail["jaccard"].max()),
                    "redundant": bool(
                        median_jaccard >= float(redundancy_threshold)
                    ),
                    "interpretation": (
                        "REDUNDANT"
                        if median_jaccard >= float(redundancy_threshold)
                        else "DISTINCT"
                    ),
                }
            )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        ["median_jaccard", "markets_compared"],
        ascending=[False, False],
    ).reset_index(drop=True)


def cross_market_parameter_neighborhood(
    cross_scan: pd.DataFrame,
    candidate,
) -> pd.DataFrame:
    """Return direct window/threshold neighbors for the same hypothesis family."""
    if cross_scan is None or cross_scan.empty:
        return pd.DataFrame()

    candidate = pd.Series(candidate)
    work = cross_scan.copy()

    same = (
        work["candidate_type"].astype(str).eq(
            str(candidate.get("candidate_type"))
        )
        & work["feature"].astype(str).eq(
            str(candidate.get("feature"))
        )
        & pd.to_numeric(
            work["horizon_weeks"],
            errors="coerce",
        ).eq(float(candidate.get("horizon_weeks")))
    )

    target_q = candidate.get("flow_quantile")
    q_values = pd.to_numeric(work["flow_quantile"], errors="coerce")
    if pd.isna(target_q):
        same &= q_values.isna()
    else:
        same &= np.isclose(
            q_values.to_numpy(dtype=float),
            float(target_q),
            equal_nan=False,
        )

    family = work.loc[same].copy()
    if family.empty:
        return pd.DataFrame()

    windows = sorted(
        {
            int(x)
            for x in pd.to_numeric(
                family["window_weeks"],
                errors="coerce",
            ).dropna()
        }
    )
    thresholds = sorted(
        {
            float(x)
            for x in pd.to_numeric(
                family["threshold_upper"],
                errors="coerce",
            ).dropna()
        }
    )

    target_w = int(candidate["window_weeks"])
    target_t = float(candidate["threshold_upper"])

    try:
        w_idx = windows.index(target_w)
        t_idx = thresholds.index(target_t)
    except ValueError:
        return pd.DataFrame()

    allowed = {(target_w, target_t, "CENTER")}

    if w_idx > 0:
        allowed.add((windows[w_idx - 1], target_t, "WINDOW -1"))
    if w_idx < len(windows) - 1:
        allowed.add((windows[w_idx + 1], target_t, "WINDOW +1"))
    if t_idx > 0:
        allowed.add((target_w, thresholds[t_idx - 1], "THRESHOLD -1"))
    if t_idx < len(thresholds) - 1:
        allowed.add((target_w, thresholds[t_idx + 1], "THRESHOLD +1"))

    labels = {
        (int(w), float(t)): label
        for w, t, label in allowed
    }

    mask = family.apply(
        lambda r: (
            int(r["window_weeks"]),
            float(r["threshold_upper"]),
        )
        in labels,
        axis=1,
    )
    out = family.loc[mask].copy()
    out["neighbor_role"] = out.apply(
        lambda r: labels[
            (
                int(r["window_weeks"]),
                float(r["threshold_upper"]),
            )
        ],
        axis=1,
    )

    order = {
        "CENTER": 0,
        "WINDOW -1": 1,
        "WINDOW +1": 2,
        "THRESHOLD -1": 3,
        "THRESHOLD +1": 4,
    }
    out["_order"] = out["neighbor_role"].map(order).fillna(99)
    return out.sort_values("_order").drop(columns=["_order"]).reset_index(
        drop=True
    )


def cross_market_neighborhood_summary(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {
            "neighbor_count": 0,
            "positive_neighbor_share": np.nan,
            "median_neighbor_score": np.nan,
            "stable_region": False,
        }

    neighbors = table[
        table["neighbor_role"].astype(str).ne("CENTER")
    ].copy()
    if neighbors.empty:
        return {
            "neighbor_count": 0,
            "positive_neighbor_share": np.nan,
            "median_neighbor_score": np.nan,
            "stable_region": False,
        }

    positive_share = pd.to_numeric(
        neighbors["positive_validation_share"],
        errors="coerce",
    )
    scores = pd.to_numeric(
        neighbors["cross_market_score"],
        errors="coerce",
    )

    positive_neighbor_share = float(
        (positive_share >= 0.60).mean()
    )
    median_neighbor_score = (
        float(scores.median())
        if scores.notna().any()
        else np.nan
    )

    stable_region = bool(
        len(neighbors) >= 2
        and positive_neighbor_share >= 0.67
        and np.isfinite(median_neighbor_score)
        and median_neighbor_score >= 62.0
    )

    return {
        "neighbor_count": int(len(neighbors)),
        "positive_neighbor_share": positive_neighbor_share,
        "median_neighbor_score": median_neighbor_score,
        "stable_region": stable_region,
    }

CORE_FX_UNIVERSE_SIZE = 7


def fixed_parameter_region_matrix(
    cross_scan: pd.DataFrame,
    candidate,
    *,
    windows: tuple[int, ...] = (104, 156, 208),
    thresholds: tuple[float, ...] = (70.0, 75.0, 80.0),
) -> pd.DataFrame:
    """Fixed pre-declared 3x3 region; never invents intermediate parameters."""
    if cross_scan is None or cross_scan.empty:
        return pd.DataFrame()

    candidate = pd.Series(candidate)
    work = cross_scan.copy()

    same = (
        work["candidate_type"].astype(str).eq(
            str(candidate.get("candidate_type"))
        )
        & work["feature"].astype(str).eq(
            str(candidate.get("feature"))
        )
        & pd.to_numeric(
            work["horizon_weeks"],
            errors="coerce",
        ).eq(float(candidate.get("horizon_weeks")))
    )

    target_q = candidate.get("flow_quantile")
    q_values = pd.to_numeric(work["flow_quantile"], errors="coerce")
    if pd.isna(target_q):
        same &= q_values.isna()
    else:
        same &= np.isclose(
            q_values.to_numpy(dtype=float),
            float(target_q),
            equal_nan=False,
        )

    family = work.loc[same].copy()
    rows = []

    for window in windows:
        for threshold in thresholds:
            lower = 100.0 - float(threshold)
            cell = family.loc[
                pd.to_numeric(
                    family["window_weeks"],
                    errors="coerce",
                ).eq(float(window))
                & np.isclose(
                    pd.to_numeric(
                        family["threshold_upper"],
                        errors="coerce",
                    ).to_numpy(dtype=float),
                    float(threshold),
                    equal_nan=False,
                )
            ]

            if cell.empty:
                rows.append(
                    {
                        "window_weeks": int(window),
                        "threshold_upper": float(threshold),
                        "threshold_lower": lower,
                        "available": False,
                        "markets_eligible": 0,
                        "positive_validation_share": np.nan,
                        "train_validation_positive_share": np.nan,
                        "median_validation_return": np.nan,
                        "cross_market_score": np.nan,
                        "cross_market_status": "NOT AVAILABLE",
                    }
                )
                continue

            row = cell.sort_values(
                ["cross_market_score", "markets_eligible"],
                ascending=[False, False],
            ).iloc[0]

            rows.append(
                {
                    "window_weeks": int(window),
                    "threshold_upper": float(threshold),
                    "threshold_lower": lower,
                    "available": True,
                    "markets_eligible": int(
                        row.get("markets_eligible", 0) or 0
                    ),
                    "positive_validation_share": float(
                        row.get("positive_validation_share", np.nan)
                    ),
                    "train_validation_positive_share": float(
                        row.get(
                            "train_validation_positive_share",
                            np.nan,
                        )
                    ),
                    "median_validation_return": float(
                        row.get("median_validation_return", np.nan)
                    ),
                    "cross_market_score": float(
                        row.get("cross_market_score", np.nan)
                    ),
                    "cross_market_status": str(
                        row.get("cross_market_status", "")
                    ),
                }
            )

    return pd.DataFrame(rows)


def candidate_flow_overlap(
    redundancy: pd.DataFrame,
    candidate_rank: int | float | None,
) -> dict:
    if (
        redundancy is None
        or redundancy.empty
        or candidate_rank is None
        or pd.isna(candidate_rank)
    ):
        return {
            "max_median_jaccard": np.nan,
            "counterpart_rank": None,
            "pairs": 0,
        }

    rank = int(candidate_rank)
    subset = redundancy[
        redundancy["rank_a"].eq(rank)
        | redundancy["rank_b"].eq(rank)
    ].copy()

    if subset.empty:
        return {
            "max_median_jaccard": np.nan,
            "counterpart_rank": None,
            "pairs": 0,
        }

    subset["median_jaccard"] = pd.to_numeric(
        subset["median_jaccard"],
        errors="coerce",
    )
    subset = subset.dropna(subset=["median_jaccard"])
    if subset.empty:
        return {
            "max_median_jaccard": np.nan,
            "counterpart_rank": None,
            "pairs": 0,
        }

    top = subset.sort_values(
        "median_jaccard",
        ascending=False,
    ).iloc[0]

    counterpart = (
        int(top["rank_b"])
        if int(top["rank_a"]) == rank
        else int(top["rank_a"])
    )

    return {
        "max_median_jaccard": float(top["median_jaccard"]),
        "counterpart_rank": counterpart,
        "pairs": int(len(subset)),
    }


def evaluate_pre_oos_decision_gate(
    candidate,
    *,
    selected_markets_total: int,
    loaded_markets_total: int,
    lomo_summary: Mapping[str, object],
    neighborhood_summary: Mapping[str, object],
    max_median_jaccard: float = np.nan,
    core_universe_size: int = CORE_FX_UNIVERSE_SIZE,
) -> dict:
    """Fixed V3.12E pre-OOS gate.

    The gate is diagnostic, not an optimizer. It evaluates the already-selected
    candidate against pre-declared criteria and never reads OOS.
    """
    row = pd.Series(candidate)

    eligible = int(row.get("markets_eligible", 0) or 0)
    positive_share = float(
        row.get("positive_validation_share", np.nan)
    )
    replicated_share = float(
        row.get("train_validation_positive_share", np.nan)
    )
    median_n_validation = float(
        row.get("median_n_validation", np.nan)
    )

    selected = int(selected_markets_total)
    loaded = int(loaded_markets_total)
    universe_complete = selected >= int(core_universe_size)

    positive_count = int(
        row.get("positive_validation_markets", 0) or 0
    )
    positive_of_selected = (
        positive_count / selected
        if selected > 0
        else np.nan
    )

    criteria = []

    # 1) Coverage: full predeclared core universe must remain selected.
    if (
        universe_complete
        and eligible >= 5
        and np.isfinite(positive_share)
        and positive_share >= 0.70
        and np.isfinite(positive_of_selected)
        and positive_of_selected >= 0.50
    ):
        coverage_status = "PASS"
    elif (
        selected >= 6
        and eligible >= 4
        and np.isfinite(positive_share)
        and positive_share >= 0.60
    ):
        coverage_status = "WATCH"
    else:
        coverage_status = "FAIL"

    criteria.append(
        {
            "criterion": "Cross-Market Coverage",
            "status": coverage_status,
            "value": (
                f"{positive_count} positiv / {eligible} eligible / "
                f"{loaded} loaded / {selected} selected"
            ),
            "rule": (
                "PASS: vollständiges 7er Core-FX-Universum gewählt, "
                "≥5 eligible, ≥70% eligible positiv und ≥50% aller "
                "gewählten Märkte positiv."
            ),
        }
    )

    # 2) Train -> Validation replication.
    if np.isfinite(replicated_share) and replicated_share >= 0.65:
        replication_status = "PASS"
    elif np.isfinite(replicated_share) and replicated_share >= 0.50:
        replication_status = "WATCH"
    else:
        replication_status = "FAIL"

    criteria.append(
        {
            "criterion": "Train→Validation Replication",
            "status": replication_status,
            "value": (
                "—"
                if not np.isfinite(replicated_share)
                else f"{replicated_share:.0%}"
            ),
            "rule": "PASS ≥65%; WATCH 50–64%; FAIL <50%.",
        }
    )

    # 3) Leave-one-market-out.
    lomo_stable = bool(lomo_summary.get("stable", False))
    worst_score = float(lomo_summary.get("worst_score", np.nan))
    max_delta = float(lomo_summary.get("max_abs_delta", np.nan))
    positive_min = float(
        lomo_summary.get("positive_share_min", np.nan)
    )

    if lomo_stable:
        lomo_status = "PASS"
    elif (
        np.isfinite(worst_score)
        and worst_score >= 62.0
        and np.isfinite(max_delta)
        and max_delta <= 15.0
        and np.isfinite(positive_min)
        and positive_min >= 0.50
    ):
        lomo_status = "WATCH"
    else:
        lomo_status = "FAIL"

    criteria.append(
        {
            "criterion": "Leave-One-Market-Out",
            "status": lomo_status,
            "value": (
                f"Worst {worst_score:.1f} · Δmax {max_delta:.1f}"
                if np.isfinite(worst_score) and np.isfinite(max_delta)
                else "—"
            ),
            "rule": (
                "PASS nach bestehender LOMO-Stabilitätsregel; WATCH nur bei "
                "Worst Score ≥62, Δ≤15 und min. 50% Val positiv."
            ),
        }
    )

    # 4) Fixed parameter region. This is deliberately a soft blocker:
    # a point optimum becomes HOLD, not automatic REJECT.
    region_stable = bool(
        neighborhood_summary.get("stable_region", False)
    )
    neighbor_positive = float(
        neighborhood_summary.get(
            "positive_neighbor_share",
            np.nan,
        )
    )
    median_neighbor_score = float(
        neighborhood_summary.get(
            "median_neighbor_score",
            np.nan,
        )
    )

    if region_stable:
        region_status = "PASS"
    elif (
        np.isfinite(neighbor_positive)
        and neighbor_positive >= 0.50
        and np.isfinite(median_neighbor_score)
        and median_neighbor_score >= 60.0
    ):
        region_status = "WATCH"
    else:
        region_status = "FAIL"

    criteria.append(
        {
            "criterion": "Parameter Region",
            "status": region_status,
            "value": (
                "—"
                if not np.isfinite(neighbor_positive)
                else f"{neighbor_positive:.0%} direkte Nachbarn positiv"
            ),
            "rule": (
                "PASS: bestehende stabile Region; WATCH: ≥50% direkte "
                "Nachbarn positiv und Median-Score ≥60; sonst FAIL."
            ),
        }
    )

    # 5) Redundancy is a family diagnostic, not a hard invalidation.
    candidate_type = str(row.get("candidate_type", ""))
    if candidate_type != "FLOW":
        redundancy_status = "N/A"
        redundancy_value = "STATE-Kandidat"
    elif not np.isfinite(max_median_jaccard):
        redundancy_status = "WATCH"
        redundancy_value = "keine belastbare Paarmessung"
    elif max_median_jaccard < 0.65:
        redundancy_status = "PASS"
        redundancy_value = f"{max_median_jaccard:.0%} max Median Jaccard"
    elif max_median_jaccard < 0.80:
        redundancy_status = "WATCH"
        redundancy_value = f"{max_median_jaccard:.0%} max Median Jaccard"
    else:
        redundancy_status = "WATCH"
        redundancy_value = (
            f"{max_median_jaccard:.0%} · als Flow-Familie behandeln"
        )

    criteria.append(
        {
            "criterion": "Flow Redundancy",
            "status": redundancy_status,
            "value": redundancy_value,
            "rule": (
                "PASS <65%; WATCH 65–79%; ab 80% nicht als unabhängige "
                "Bestätigung zählen. Redundanz allein erzeugt keinen REJECT."
            ),
        }
    )

    # 6) Sample adequacy.
    if (
        eligible >= 5
        and np.isfinite(median_n_validation)
        and median_n_validation >= 4
    ):
        sample_status = "PASS"
    elif (
        eligible >= 4
        and np.isfinite(median_n_validation)
        and median_n_validation >= 4
    ):
        sample_status = "WATCH"
    else:
        sample_status = "FAIL"

    criteria.append(
        {
            "criterion": "Sample Adequacy",
            "status": sample_status,
            "value": (
                f"{eligible} eligible · Median nVal "
                f"{median_n_validation:.1f}"
                if np.isfinite(median_n_validation)
                else f"{eligible} eligible · Median nVal —"
            ),
            "rule": (
                "PASS: ≥5 eligible Märkte und Median nValidation ≥4; "
                "WATCH bei 4 Märkten; sonst FAIL."
            ),
        }
    )

    criteria_frame = pd.DataFrame(criteria)

    hard_criteria = {
        "Cross-Market Coverage",
        "Train→Validation Replication",
        "Leave-One-Market-Out",
        "Sample Adequacy",
    }
    hard_fail = bool(
        (
            criteria_frame["criterion"].isin(hard_criteria)
            & criteria_frame["status"].eq("FAIL")
        ).any()
    )

    non_pass = criteria_frame[
        ~criteria_frame["status"].isin(["PASS", "N/A"])
    ]

    if hard_fail:
        verdict = "REJECT"
    elif non_pass.empty:
        verdict = "PASS"
    else:
        verdict = "HOLD"

    return {
        "verdict": verdict,
        "criteria": criteria_frame,
        "pass_count": int(
            criteria_frame["status"].eq("PASS").sum()
        ),
        "watch_count": int(
            criteria_frame["status"].eq("WATCH").sum()
        ),
        "fail_count": int(
            criteria_frame["status"].eq("FAIL").sum()
        ),
        "universe_complete": bool(universe_complete),
        "positive_of_selected_share": positive_of_selected,
    }
