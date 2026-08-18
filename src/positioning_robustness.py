from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


DEFAULT_FLOW_FEATURES = (
    "pct_release_velocity_1w",
    "pct_release_velocity_2w",
    "pct_release_velocity_4w",
    "raw_release_velocity_1w",
    "raw_release_velocity_2w",
    "raw_release_velocity_4w",
    "net_oi_release_velocity_1w",
    "net_oi_release_velocity_2w",
    "net_oi_release_velocity_4w",
    "pct_release_acceleration",
    "raw_release_acceleration",
    "net_oi_release_acceleration",
)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def add_research_time_split(
    events: pd.DataFrame,
    *,
    date_col: str = "release_report_date",
    train_share: float = 0.60,
    validation_share: float = 0.20,
    min_unique_dates: int = 8,
) -> tuple[pd.DataFrame, dict]:
    """Assign one shared chronological Train/Validation/OOS split.

    The split is based on unique event dates across the full candidate universe.
    Therefore the same historical release date can never be Train for one
    parameter definition and Validation/OOS for another.

    OOS is intentionally *not* used by the ranking score.
    """
    if events is None or events.empty or date_col not in events.columns:
        return pd.DataFrame(), {}

    train_share = float(train_share)
    validation_share = float(validation_share)
    if not (0.0 < train_share < 1.0):
        raise ValueError("train_share muss zwischen 0 und 1 liegen")
    if not (0.0 < validation_share < 1.0):
        raise ValueError("validation_share muss zwischen 0 und 1 liegen")
    if train_share + validation_share >= 1.0:
        raise ValueError("Train + Validation müssen Platz für OOS lassen")

    out = events.copy()
    out["_research_date"] = pd.to_datetime(out[date_col], errors="coerce")
    valid_dates = pd.Series(out["_research_date"].dropna().unique()).sort_values().reset_index(drop=True)

    if len(valid_dates) < int(min_unique_dates):
        out["research_split"] = pd.NA
        return out.drop(columns=["_research_date"]), {
            "enough_history": False,
            "unique_dates": int(len(valid_dates)),
            "train_end": pd.NaT,
            "validation_end": pd.NaT,
        }

    n_dates = len(valid_dates)
    train_count = max(1, int(np.floor(n_dates * train_share)))
    validation_count = max(1, int(np.floor(n_dates * validation_share)))

    # Guarantee at least one unique OOS date.
    if train_count + validation_count >= n_dates:
        validation_count = max(1, n_dates - train_count - 1)
    if train_count + validation_count >= n_dates:
        train_count = max(1, n_dates - validation_count - 1)

    train_end = pd.Timestamp(valid_dates.iloc[train_count - 1])
    validation_end = pd.Timestamp(valid_dates.iloc[train_count + validation_count - 1])

    out["research_split"] = np.select(
        [
            out["_research_date"].notna() & (out["_research_date"] <= train_end),
            out["_research_date"].notna()
            & (out["_research_date"] > train_end)
            & (out["_research_date"] <= validation_end),
            out["_research_date"].notna() & (out["_research_date"] > validation_end),
        ],
        ["TRAIN", "VALIDATION", "OOS"],
        default=pd.NA,
    )

    meta = {
        "enough_history": True,
        "unique_dates": int(n_dates),
        "train_end": train_end,
        "validation_end": validation_end,
        "train_unique_dates": int(train_count),
        "validation_unique_dates": int(validation_count),
        "oos_unique_dates": int(n_dates - train_count - validation_count),
    }
    return out.drop(columns=["_research_date"]), meta


def _return_stats(frame: pd.DataFrame, return_col: str) -> dict:
    if frame is None or frame.empty or return_col not in frame.columns:
        return {"n": 0, "median": np.nan, "mean": np.nan, "hit_rate": np.nan}

    values = _numeric(frame[return_col]).dropna()
    if values.empty:
        return {"n": 0, "median": np.nan, "mean": np.nan, "hit_rate": np.nan}

    return {
        "n": int(len(values)),
        "median": float(values.median()),
        "mean": float(values.mean()),
        "hit_rate": float((values > 0).mean()),
    }


def _candidate_stats(frame: pd.DataFrame, return_col: str) -> dict:
    row: dict = {}
    for split_name, prefix in (
        ("TRAIN", "train"),
        ("VALIDATION", "validation"),
        ("OOS", "oos"),
    ):
        stats = _return_stats(
            frame[frame["research_split"] == split_name],
            return_col,
        )
        row[f"n_{prefix}"] = stats["n"]
        row[f"{prefix}_median"] = stats["median"]
        row[f"{prefix}_mean"] = stats["mean"]
        row[f"{prefix}_hit_rate"] = stats["hit_rate"]
    return row


def _positive(value) -> bool:
    try:
        return bool(np.isfinite(float(value)) and float(value) > 0.0)
    except (TypeError, ValueError):
        return False


def _base_train_validation_score(row: pd.Series) -> float:
    """Transparent 0-80 score before neighborhood stability.

    OOS is deliberately absent.

    Components:
      15  positive Train median
      25  positive Validation median
      15  magnitude retention from Train to Validation
      25  sample adequacy (Train and Validation)
    """
    train_median = float(row.get("train_median", np.nan))
    validation_median = float(row.get("validation_median", np.nan))
    n_train = int(row.get("n_train", 0) or 0)
    n_validation = int(row.get("n_validation", 0) or 0)

    score = 0.0
    if _positive(train_median):
        score += 15.0
    if _positive(validation_median):
        score += 25.0

    if _positive(train_median) and _positive(validation_median):
        ratio = validation_median / train_median
        if ratio > 0 and np.isfinite(ratio):
            # 1.0 when equal; decays symmetrically when Validation is much
            # weaker/stronger than Train. This rewards retention, not magnitude.
            retention = float(np.exp(-abs(np.log(ratio))))
            score += 15.0 * retention

    score += 12.5 * min(1.0, n_train / 20.0)
    score += 12.5 * min(1.0, n_validation / 8.0)
    return float(score)


def _family_key(candidate_type: str, feature: str, flow_quantile) -> str:
    if candidate_type == "STATE":
        return "STATE"
    return f"FLOW::{feature}::Q{float(flow_quantile):.2f}"


def _add_neighborhood_robustness(scan: pd.DataFrame) -> pd.DataFrame:
    """Reward parameter *regions* instead of isolated best cells."""
    if scan.empty:
        return scan

    out = scan.copy()
    windows = sorted(int(x) for x in out["window_weeks"].dropna().unique())
    thresholds = sorted(float(x) for x in out["threshold_upper"].dropna().unique())
    w_pos = {value: i for i, value in enumerate(windows)}
    t_pos = {value: i for i, value in enumerate(thresholds)}

    shares: list[float] = []
    counts: list[int] = []

    for _, row in out.iterrows():
        family = row["candidate_family"]
        w = int(row["window_weeks"])
        t = float(row["threshold_upper"])
        wi = w_pos[w]
        ti = t_pos[t]

        family_rows = out[out["candidate_family"] == family]
        neighbors = family_rows[
            family_rows.apply(
                lambda r: (
                    abs(w_pos[int(r["window_weeks"])] - wi)
                    + abs(t_pos[float(r["threshold_upper"])] - ti)
                )
                == 1,
                axis=1,
            )
        ]

        if neighbors.empty:
            shares.append(np.nan)
            counts.append(0)
            continue

        positive = (
            _numeric(neighbors["train_median"]).gt(0)
            & _numeric(neighbors["validation_median"]).gt(0)
        )
        shares.append(float(positive.mean()))
        counts.append(int(len(neighbors)))

    out["neighbor_positive_share"] = shares
    out["neighbor_count"] = counts
    return out


def _finalize_scores(
    scan: pd.DataFrame,
    *,
    min_train: int,
    min_validation: int,
) -> pd.DataFrame:
    if scan.empty:
        return scan

    out = _add_neighborhood_robustness(scan)
    out["base_score_train_validation"] = out.apply(_base_train_validation_score, axis=1)
    neighborhood = _numeric(out["neighbor_positive_share"]).fillna(0.0).clip(0.0, 1.0)
    out["robustness_score"] = (
        out["base_score_train_validation"] + 20.0 * neighborhood
    ).clip(0.0, 100.0)

    out["sample_ok"] = (
        _numeric(out["n_train"]).ge(int(min_train))
        & _numeric(out["n_validation"]).ge(int(min_validation))
    )

    def status(row: pd.Series) -> str:
        if not bool(row["sample_ok"]):
            return "INSUFFICIENT SAMPLE"
        score = float(row["robustness_score"])
        if score >= 75:
            return "ROBUST CANDIDATE"
        if score >= 60:
            return "PROMISING"
        if score >= 45:
            return "EXPLORATORY"
        return "WEAK"

    out["status"] = out.apply(status, axis=1)

    # OOS is descriptive only and never enters robustness_score.
    def oos_status(row: pd.Series) -> str:
        if int(row.get("n_oos", 0) or 0) < 2:
            return "INSUFFICIENT"
        value = float(row.get("oos_median", np.nan))
        if not np.isfinite(value):
            return "INSUFFICIENT"
        return "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "FLAT"

    out["oos_status"] = out.apply(oos_status, axis=1)

    eligible = out["sample_ok"].astype(bool)
    out["rank_train_validation"] = np.nan
    if eligible.any():
        ranked_idx = (
            out.loc[eligible]
            .sort_values(
                ["robustness_score", "validation_median", "n_validation"],
                ascending=[False, False, False],
            )
            .index
        )
        out.loc[ranked_idx, "rank_train_validation"] = np.arange(1, len(ranked_idx) + 1)

    return out.sort_values(
        ["sample_ok", "robustness_score", "validation_median"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def scan_parameter_robustness(
    events: pd.DataFrame,
    *,
    horizon_weeks: int = 8,
    flow_features: Sequence[str] = DEFAULT_FLOW_FEATURES,
    flow_quantiles: Sequence[float] = (0.50, 0.75),
    train_share: float = 0.60,
    validation_share: float = 0.20,
    min_train: int = 8,
    min_validation: int = 4,
) -> tuple[pd.DataFrame, dict]:
    """Automatically scan state and high-flow parameter regions.

    Ranking uses Train + Validation only.

    STATE candidates:
      every available window × threshold pair.

    FLOW candidates:
      same state pair + one release-flow feature + a high-flow cutoff.
      The numeric cutoff is estimated from TRAIN only and then frozen for
      Validation/OOS. This prevents quantile leakage from later periods.

    OOS columns are returned for a later locked reveal, but are excluded from
    ranking and robustness_score.
    """
    if events is None or events.empty:
        return pd.DataFrame(), {}

    horizon = int(horizon_weeks)
    ret_col = f"directional_return_{horizon}w"
    if ret_col not in events.columns:
        return pd.DataFrame(), {}

    work = events.copy()
    if "release_available" in work.columns:
        work = work[work["release_available"].fillna(False)].copy()
    work[ret_col] = _numeric(work[ret_col])
    work = work.dropna(subset=["release_report_date", "window_weeks", "threshold_upper"])

    split, meta = add_research_time_split(
        work,
        train_share=train_share,
        validation_share=validation_share,
    )
    if split.empty or not meta.get("enough_history", False):
        return pd.DataFrame(), meta

    rows: list[dict] = []

    group_cols = ["window_weeks", "threshold_upper", "threshold_lower"]
    for (window, upper, lower), combo in split.groupby(group_cols, dropna=False):
        baseline = {
            "candidate_type": "STATE",
            "feature": "STATE",
            "flow_quantile": np.nan,
            "flow_cutoff_train": np.nan,
            "window_weeks": int(window),
            "threshold_upper": float(upper),
            "threshold_lower": float(lower),
            "horizon_weeks": horizon,
        }
        baseline["candidate_family"] = _family_key("STATE", "STATE", np.nan)
        baseline.update(_candidate_stats(combo, ret_col))
        rows.append(baseline)

        train_combo = combo[combo["research_split"] == "TRAIN"]

        for feature in flow_features:
            if feature not in combo.columns:
                continue

            train_values = _numeric(train_combo[feature]).dropna()
            if len(train_values) < max(6, int(min_train)):
                continue

            for q in flow_quantiles:
                q = float(q)
                if not (0.0 < q < 1.0):
                    raise ValueError("flow_quantiles müssen zwischen 0 und 1 liegen")

                cutoff = float(train_values.quantile(q))
                filtered = combo[_numeric(combo[feature]) >= cutoff].copy()

                candidate = {
                    "candidate_type": "FLOW",
                    "feature": str(feature),
                    "flow_quantile": q,
                    "flow_cutoff_train": cutoff,
                    "window_weeks": int(window),
                    "threshold_upper": float(upper),
                    "threshold_lower": float(lower),
                    "horizon_weeks": horizon,
                }
                candidate["candidate_family"] = _family_key(
                    "FLOW",
                    str(feature),
                    q,
                )
                candidate.update(_candidate_stats(filtered, ret_col))
                rows.append(candidate)

    scan = pd.DataFrame(rows)
    if scan.empty:
        return scan, meta

    scan = _finalize_scores(
        scan,
        min_train=int(min_train),
        min_validation=int(min_validation),
    )
    meta = {
        **meta,
        "horizon_weeks": horizon,
        "candidate_count": int(len(scan)),
        "eligible_count": int(scan["sample_ok"].sum()),
        "robust_count": int((scan["status"] == "ROBUST CANDIDATE").sum()),
        "oos_used_in_score": False,
    }
    return scan, meta


def scanner_findings(scan: pd.DataFrame) -> dict:
    """Return compact, non-production research findings."""
    if scan is None or scan.empty:
        return {
            "top_state": None,
            "top_flow": None,
            "robust_count": 0,
            "eligible_count": 0,
        }

    eligible = scan[scan["sample_ok"].fillna(False)].copy()
    if eligible.empty:
        return {
            "top_state": None,
            "top_flow": None,
            "robust_count": 0,
            "eligible_count": 0,
        }

    state = eligible[eligible["candidate_type"] == "STATE"]
    flow = eligible[eligible["candidate_type"] == "FLOW"]

    top_state = state.iloc[0].to_dict() if not state.empty else None
    top_flow = flow.iloc[0].to_dict() if not flow.empty else None

    return {
        "top_state": top_state,
        "top_flow": top_flow,
        "robust_count": int((eligible["status"] == "ROBUST CANDIDATE").sum()),
        "eligible_count": int(len(eligible)),
    }

def _candidate_label(row: pd.Series) -> str:
    candidate_type = str(row.get("candidate_type", "STATE"))
    window = int(row.get("window_weeks", 0) or 0)
    upper = float(row.get("threshold_upper", np.nan))
    lower = float(row.get("threshold_lower", np.nan))
    if candidate_type == "STATE":
        return f"{window}W · {upper:.0f}/{lower:.0f} · STATE"
    feature = str(row.get("feature", "FLOW"))
    q = float(row.get("flow_quantile", np.nan))
    q_text = f"Q{q:.2f}" if np.isfinite(q) else "Q—"
    return f"{window}W · {upper:.0f}/{lower:.0f} · {feature} · {q_text}"


def candidate_event_dates(
    events: pd.DataFrame,
    candidate,
    *,
    train_share: float = 0.60,
    validation_share: float = 0.20,
    include_splits: Sequence[str] = ("TRAIN", "VALIDATION"),
) -> set[pd.Timestamp]:
    """Return the event dates selected by one candidate without using OOS."""
    if events is None or events.empty:
        return set()

    work = events.copy()
    if "release_available" in work.columns:
        work = work[work["release_available"].fillna(False)].copy()

    split, meta = add_research_time_split(
        work,
        train_share=train_share,
        validation_share=validation_share,
    )
    if split.empty or not meta.get("enough_history", False):
        return set()

    row = pd.Series(candidate)
    mask = (
        _numeric(split["window_weeks"]).eq(int(row["window_weeks"]))
        & _numeric(split["threshold_upper"]).eq(float(row["threshold_upper"]))
        & split["research_split"].isin(tuple(include_splits))
    )

    if str(row.get("candidate_type", "STATE")) == "FLOW":
        feature = str(row.get("feature", ""))
        cutoff = float(row.get("flow_cutoff_train", np.nan))
        if feature not in split.columns or not np.isfinite(cutoff):
            return set()
        mask &= _numeric(split[feature]).ge(cutoff)

    dates = pd.to_datetime(
        split.loc[mask, "release_report_date"],
        errors="coerce",
    ).dropna()
    return {pd.Timestamp(x) for x in dates.unique()}


def candidate_overlap_table(
    events: pd.DataFrame,
    scan: pd.DataFrame,
    *,
    top_n: int = 6,
    train_share: float = 0.60,
    validation_share: float = 0.20,
) -> pd.DataFrame:
    """Compare whether top FLOW candidates select the same historical episodes."""
    if events is None or events.empty or scan is None or scan.empty:
        return pd.DataFrame()

    candidates = scan[
        scan["sample_ok"].fillna(False)
        & scan["candidate_type"].eq("FLOW")
    ].sort_values(
        ["rank_train_validation", "robustness_score"],
        ascending=[True, False],
    ).head(int(top_n))

    if len(candidates) < 2:
        return pd.DataFrame()

    cached_sets = {}
    rows = []
    candidate_rows = list(candidates.iterrows())

    for idx, row in candidate_rows:
        cached_sets[idx] = candidate_event_dates(
            events,
            row,
            train_share=train_share,
            validation_share=validation_share,
        )

    for i in range(len(candidate_rows)):
        idx_a, row_a = candidate_rows[i]
        set_a = cached_sets[idx_a]
        for j in range(i + 1, len(candidate_rows)):
            idx_b, row_b = candidate_rows[j]
            set_b = cached_sets[idx_b]

            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            smaller = min(len(set_a), len(set_b))

            jaccard = intersection / union if union else np.nan
            overlap_coefficient = intersection / smaller if smaller else np.nan

            if np.isfinite(jaccard) and jaccard >= 0.80:
                interpretation = "NAHEZU GLEICHE EVENTS"
            elif np.isfinite(jaccard) and jaccard >= 0.50:
                interpretation = "STARKER OVERLAP"
            else:
                interpretation = "EHER UNTERSCHIEDLICH"

            rows.append(
                {
                    "candidate_a": _candidate_label(row_a),
                    "candidate_b": _candidate_label(row_b),
                    "n_a": int(len(set_a)),
                    "n_b": int(len(set_b)),
                    "intersection": int(intersection),
                    "jaccard": float(jaccard) if np.isfinite(jaccard) else np.nan,
                    "overlap_coefficient": (
                        float(overlap_coefficient)
                        if np.isfinite(overlap_coefficient)
                        else np.nan
                    ),
                    "interpretation": interpretation,
                }
            )

    return pd.DataFrame(rows).sort_values(
        ["jaccard", "intersection"],
        ascending=[False, False],
    ).reset_index(drop=True)


def incremental_value_table(
    scan: pd.DataFrame,
    *,
    top_n: int = 20,
) -> pd.DataFrame:
    """Compare each FLOW candidate with its exact matching STATE baseline."""
    if scan is None or scan.empty:
        return pd.DataFrame()

    state = scan[scan["candidate_type"].eq("STATE")].copy()
    flow = scan[
        scan["candidate_type"].eq("FLOW")
        & scan["sample_ok"].fillna(False)
    ].sort_values(
        ["rank_train_validation", "robustness_score"],
        ascending=[True, False],
    ).head(int(top_n))

    rows = []
    for _, row in flow.iterrows():
        baseline = state[
            _numeric(state["window_weeks"]).eq(int(row["window_weeks"]))
            & _numeric(state["threshold_upper"]).eq(float(row["threshold_upper"]))
            & _numeric(state["horizon_weeks"]).eq(int(row["horizon_weeks"]))
        ]
        if baseline.empty:
            continue

        base = baseline.iloc[0]
        n_state_val = int(base.get("n_validation", 0) or 0)
        n_flow_val = int(row.get("n_validation", 0) or 0)

        rows.append(
            {
                "parameter": (
                    f"{int(row['window_weeks'])}W · "
                    f"{float(row['threshold_upper']):.0f}/"
                    f"{float(row['threshold_lower']):.0f}"
                ),
                "feature": str(row["feature"]),
                "flow_quantile": float(row["flow_quantile"]),
                "flow_cutoff_train": float(row["flow_cutoff_train"]),
                "train_median_lift": (
                    float(row.get("train_median", np.nan))
                    - float(base.get("train_median", np.nan))
                ),
                "validation_median_lift": (
                    float(row.get("validation_median", np.nan))
                    - float(base.get("validation_median", np.nan))
                ),
                "validation_hit_rate_lift": (
                    float(row.get("validation_hit_rate", np.nan))
                    - float(base.get("validation_hit_rate", np.nan))
                ),
                "validation_sample_retention": (
                    n_flow_val / n_state_val if n_state_val else np.nan
                ),
                "neighbor_positive_share": float(
                    row.get("neighbor_positive_share", np.nan)
                ),
                "robustness_score": float(row.get("robustness_score", np.nan)),
            }
        )

    return pd.DataFrame(rows)


def flow_monotonicity_diagnostic(
    events: pd.DataFrame,
    candidate,
    *,
    train_share: float = 0.60,
    validation_share: float = 0.20,
) -> pd.DataFrame:
    """Test ordered flow quartiles using TRAIN-defined bins only."""
    if events is None or events.empty:
        return pd.DataFrame()

    row = pd.Series(candidate)
    if str(row.get("candidate_type", "")) != "FLOW":
        return pd.DataFrame()

    feature = str(row.get("feature", ""))
    horizon = int(row.get("horizon_weeks", 8) or 8)
    return_col = f"directional_return_{horizon}w"
    if feature not in events.columns or return_col not in events.columns:
        return pd.DataFrame()

    work = events.copy()
    if "release_available" in work.columns:
        work = work[work["release_available"].fillna(False)].copy()

    split, meta = add_research_time_split(
        work,
        train_share=train_share,
        validation_share=validation_share,
    )
    if split.empty or not meta.get("enough_history", False):
        return pd.DataFrame()

    combo = split[
        _numeric(split["window_weeks"]).eq(int(row["window_weeks"]))
        & _numeric(split["threshold_upper"]).eq(float(row["threshold_upper"]))
        & split["research_split"].isin(("TRAIN", "VALIDATION"))
    ].copy()

    combo[feature] = _numeric(combo[feature])
    combo[return_col] = _numeric(combo[return_col])

    train_values = combo.loc[
        combo["research_split"].eq("TRAIN"),
        feature,
    ].dropna()

    if len(train_values) < 8 or train_values.nunique() < 2:
        return pd.DataFrame()

    try:
        _, bins = pd.qcut(
            train_values,
            q=4,
            duplicates="drop",
            retbins=True,
        )
    except ValueError:
        return pd.DataFrame()

    bins = np.asarray(bins, dtype=float)
    if len(bins) < 3:
        return pd.DataFrame()

    bins[0] = -np.inf
    bins[-1] = np.inf
    labels = [f"Q{i+1}" for i in range(len(bins) - 1)]

    combo["flow_bucket"] = pd.cut(
        combo[feature],
        bins=bins,
        labels=labels,
        include_lowest=True,
    )

    rows = []
    for bucket in labels:
        out = {"bucket": bucket}
        for split_name, prefix in (("TRAIN", "train"), ("VALIDATION", "validation")):
            subset = combo[
                combo["research_split"].eq(split_name)
                & combo["flow_bucket"].eq(bucket)
            ]
            returns = _numeric(subset[return_col]).dropna()
            feature_values = _numeric(subset[feature]).dropna()

            out[f"n_{prefix}"] = int(len(returns))
            out[f"{prefix}_feature_median"] = (
                float(feature_values.median())
                if not feature_values.empty
                else np.nan
            )
            out[f"{prefix}_median"] = (
                float(returns.median()) if not returns.empty else np.nan
            )
            out[f"{prefix}_hit_rate"] = (
                float((returns > 0).mean()) if not returns.empty else np.nan
            )
        rows.append(out)

    return pd.DataFrame(rows)


def monotonicity_summary(diagnostic: pd.DataFrame) -> dict:
    """Summarize ordered-bucket monotonicity for Train and Validation."""
    if diagnostic is None or diagnostic.empty:
        return {
            "train_positive_steps": np.nan,
            "validation_positive_steps": np.nan,
            "train_correlation": np.nan,
            "validation_correlation": np.nan,
        }

    result = {}
    for prefix in ("train", "validation"):
        values = _numeric(diagnostic[f"{prefix}_median"]).to_numpy(dtype=float)
        values = values[np.isfinite(values)]

        if len(values) < 2:
            result[f"{prefix}_positive_steps"] = np.nan
            result[f"{prefix}_correlation"] = np.nan
            continue

        diffs = np.diff(values)
        result[f"{prefix}_positive_steps"] = float((diffs > 0).mean())

        x = np.arange(1, len(values) + 1, dtype=float)
        corr = 0.0 if np.nanstd(values) == 0 else float(np.corrcoef(x, values)[0, 1])
        result[f"{prefix}_correlation"] = corr

    return result

def _spearman_from_ordered_values(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return np.nan
    x_rank = pd.Series(np.arange(1, len(arr) + 1, dtype=float)).rank(method="average")
    y_rank = pd.Series(arr).rank(method="average")
    if float(y_rank.std(ddof=0)) == 0.0:
        return 0.0
    return float(np.corrcoef(x_rank.to_numpy(), y_rank.to_numpy())[0, 1])


def strict_monotonicity_assessment(diagnostic: pd.DataFrame) -> dict:
    empty = {
        "train_ordered": False,
        "validation_ordered": False,
        "train_spearman": np.nan,
        "validation_spearman": np.nan,
        "train_q4_q1_spread": np.nan,
        "validation_q4_q1_spread": np.nan,
        "train_positive_steps": np.nan,
        "validation_positive_steps": np.nan,
        "replicated_direction": False,
        "verdict": "INSUFFICIENT",
    }
    if diagnostic is None or diagnostic.empty:
        return empty

    if any(str(col).lower().startswith("oos") for col in diagnostic.columns):
        raise ValueError("OOS-Spalten sind in der Pre-OOS-Monotonieprüfung unzulässig")

    result = {}
    for prefix in ("train", "validation"):
        col = f"{prefix}_median"
        if col not in diagnostic.columns:
            return empty

        values = _numeric(diagnostic[col]).to_numpy(dtype=float)
        clean = values[np.isfinite(values)]

        if len(clean) < 2:
            ordered = False
            positive_steps = np.nan
            spread = np.nan
            spearman = np.nan
        else:
            diffs = np.diff(clean)
            ordered = bool(len(clean) >= 4 and np.all(diffs > 0))
            positive_steps = float((diffs > 0).mean())
            spread = float(clean[-1] - clean[0])
            spearman = _spearman_from_ordered_values(clean)

        result[f"{prefix}_ordered"] = ordered
        result[f"{prefix}_positive_steps"] = positive_steps
        result[f"{prefix}_q4_q1_spread"] = spread
        result[f"{prefix}_spearman"] = spearman

    train_spread = result["train_q4_q1_spread"]
    val_spread = result["validation_q4_q1_spread"]
    train_rho = result["train_spearman"]
    val_rho = result["validation_spearman"]
    train_steps = result["train_positive_steps"]
    val_steps = result["validation_positive_steps"]

    replicated_direction = bool(
        np.isfinite(train_spread)
        and np.isfinite(val_spread)
        and np.isfinite(train_rho)
        and np.isfinite(val_rho)
        and train_spread > 0
        and val_spread > 0
        and train_rho > 0
        and val_rho > 0
    )
    result["replicated_direction"] = replicated_direction

    if (
        result["train_ordered"]
        and result["validation_ordered"]
        and train_rho >= 0.80
        and val_rho >= 0.80
        and train_spread > 0
        and val_spread > 0
    ):
        verdict = "STRONG REPLICATED EFFECT"
    elif (
        replicated_direction
        and np.isfinite(train_steps)
        and np.isfinite(val_steps)
        and train_steps >= (2 / 3)
        and val_steps >= (2 / 3)
        and train_rho >= 0.40
        and val_rho >= 0.40
    ):
        verdict = "MODERATE REPLICATED EFFECT"
    elif replicated_direction:
        verdict = "WEAK POSITIVE TREND · NOT MONOTONIC"
    else:
        verdict = "NOT MONOTONIC"

    result["verdict"] = verdict
    return result


def _jaccard_sets(a: set[pd.Timestamp], b: set[pd.Timestamp]) -> float:
    union = len(a | b)
    if union == 0:
        return np.nan
    return float(len(a & b) / union)


def distinct_candidate_shortlist(
    events: pd.DataFrame,
    scan: pd.DataFrame,
    *,
    max_total: int = 4,
    overlap_threshold: float = 0.80,
    train_share: float = 0.60,
    validation_share: float = 0.20,
) -> pd.DataFrame:
    if events is None or events.empty or scan is None or scan.empty:
        return pd.DataFrame()

    eligible = scan[scan["sample_ok"].fillna(False)].copy()
    if eligible.empty:
        return pd.DataFrame()

    selected_rows = []
    selected_flow_sets = []

    state = eligible[eligible["candidate_type"].eq("STATE")].sort_values(
        ["rank_train_validation", "robustness_score"],
        ascending=[True, False],
    )
    if not state.empty:
        state_row = state.iloc[0].copy()
        state_row["shortlist_reason"] = "STRUCTURAL BASELINE"
        state_row["max_overlap_with_selected_flow"] = np.nan
        selected_rows.append(state_row)

    flows = eligible[eligible["candidate_type"].eq("FLOW")].sort_values(
        ["rank_train_validation", "robustness_score"],
        ascending=[True, False],
    )

    for _, row in flows.iterrows():
        if len(selected_rows) >= int(max_total):
            break

        event_set = candidate_event_dates(
            events,
            row,
            train_share=train_share,
            validation_share=validation_share,
        )
        overlaps = [
            _jaccard_sets(event_set, existing)
            for existing in selected_flow_sets
        ]
        finite_overlaps = [x for x in overlaps if np.isfinite(x)]
        max_overlap = max(finite_overlaps) if finite_overlaps else np.nan

        if np.isfinite(max_overlap) and max_overlap >= float(overlap_threshold):
            continue

        selected = row.copy()
        selected["shortlist_reason"] = (
            "TOP DISTINCT FLOW"
            if not selected_flow_sets
            else "DISTINCT FLOW HYPOTHESIS"
        )
        selected["max_overlap_with_selected_flow"] = max_overlap
        selected_rows.append(selected)
        selected_flow_sets.append(event_set)

    if not selected_rows:
        return pd.DataFrame()

    out = pd.DataFrame(selected_rows).reset_index(drop=True)
    out.insert(0, "shortlist_rank", np.arange(1, len(out) + 1))
    return out


def overlap_redundancy_summary(
    events: pd.DataFrame,
    scan: pd.DataFrame,
    *,
    top_n: int = 6,
    overlap_threshold: float = 0.80,
) -> dict:
    table = candidate_overlap_table(events, scan, top_n=top_n)
    if table.empty:
        return {
            "pairs": 0,
            "redundant_pairs": 0,
            "max_jaccard": np.nan,
        }

    jaccard = _numeric(table["jaccard"])
    return {
        "pairs": int(len(table)),
        "redundant_pairs": int((jaccard >= float(overlap_threshold)).sum()),
        "max_jaccard": float(jaccard.max()) if jaccard.notna().any() else np.nan,
    }

def build_pre_oos_freeze_snapshot(
    shortlist: pd.DataFrame,
    *,
    market_name: str,
    group_key: str,
    basis: str,
    horizon_weeks: int,
    research_version: str = "V3.11C.3",
) -> dict:
    """Create a canonical pre-OOS hypothesis snapshot without OOS fields."""
    import hashlib
    import json
    from datetime import datetime, timezone

    allowed = [
        "shortlist_rank",
        "candidate_type",
        "window_weeks",
        "threshold_upper",
        "threshold_lower",
        "feature",
        "flow_quantile",
        "flow_cutoff_train",
        "robustness_score",
        "n_train",
        "train_median",
        "n_validation",
        "validation_median",
        "neighbor_positive_share",
        "shortlist_reason",
        "max_overlap_with_selected_flow",
    ]

    records = []
    if shortlist is not None and not shortlist.empty:
        for _, row in shortlist.sort_values("shortlist_rank").iterrows():
            record = {}
            for col in allowed:
                if col not in shortlist.columns:
                    continue
                value = row.get(col)
                if pd.isna(value):
                    value = None
                elif isinstance(value, np.integer):
                    value = int(value)
                elif isinstance(value, np.floating):
                    value = float(value)
                record[col] = value
            records.append(record)

    payload = {
        "research_version": str(research_version),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "market_name": str(market_name),
        "group_key": str(group_key),
        "basis": str(basis),
        "horizon_weeks": int(horizon_weeks),
        "selection_rule": (
            "Train + Validation ranking; one structural baseline; "
            "distinct flow hypotheses with <80% Jaccard overlap; no OOS used"
        ),
        "oos_used_for_selection": False,
        "candidates": records,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["freeze_hash_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def freeze_snapshot_json(snapshot: dict) -> bytes:
    import json

    return json.dumps(
        snapshot,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")

def candidate_freeze_id(row) -> str:
    """Stable ID for one pre-OOS candidate, independent of OOS results."""
    candidate_type = str(row.get("candidate_type", "STATE"))
    window = int(row.get("window_weeks", 0) or 0)
    upper = float(row.get("threshold_upper", np.nan))
    lower = float(row.get("threshold_lower", np.nan))
    feature = str(row.get("feature", "STATE"))
    q = row.get("flow_quantile", np.nan)
    q_text = "NA" if pd.isna(q) else f"{float(q):.4f}"
    return (
        f"{candidate_type}|{window}|{upper:.4f}|{lower:.4f}|"
        f"{feature}|{q_text}"
    )


def reviewed_shortlist(
    shortlist: pd.DataFrame,
    selected_ids: Sequence[str],
) -> pd.DataFrame:
    """Return the exact manually reviewed candidate set in shortlist order."""
    if shortlist is None or shortlist.empty:
        return pd.DataFrame()

    selected = {str(x) for x in selected_ids}
    work = shortlist.copy()
    work["_freeze_id"] = work.apply(candidate_freeze_id, axis=1)
    out = work[work["_freeze_id"].isin(selected)].copy()
    out = out.sort_values("shortlist_rank").reset_index(drop=True)
    return out.drop(columns=["_freeze_id"])


def candidate_review_label(row) -> str:
    candidate_type = str(row.get("candidate_type", "STATE"))
    window = int(row.get("window_weeks", 0) or 0)
    upper = float(row.get("threshold_upper", np.nan))
    lower = float(row.get("threshold_lower", np.nan))

    if candidate_type == "STATE":
        hypothesis = "STATE ONLY"
    else:
        feature = str(row.get("feature", "FLOW"))
        labels = {
            "pct_release_velocity_1w": "Percentile Velocity 1W",
            "pct_release_velocity_2w": "Percentile Velocity 2W",
            "pct_release_velocity_4w": "Percentile Velocity 4W",
            "raw_release_velocity_1w": "Raw Velocity 1W",
            "raw_release_velocity_2w": "Raw Velocity 2W",
            "raw_release_velocity_4w": "Raw Velocity 4W",
            "net_oi_release_velocity_1w": "Net/OI Velocity 1W",
            "net_oi_release_velocity_2w": "Net/OI Velocity 2W",
            "net_oi_release_velocity_4w": "Net/OI Velocity 4W",
            "pct_release_acceleration": "Percentile Acceleration",
            "raw_release_acceleration": "Raw Acceleration",
            "net_oi_release_acceleration": "Net/OI Acceleration",
        }
        hypothesis = labels.get(feature, feature)

    score = row.get("robustness_score", np.nan)
    score_text = "—" if pd.isna(score) else f"{float(score):.1f}"
    return (
        f"{window}W · {upper:.0f}/{lower:.0f} · "
        f"{hypothesis} · Robustness {score_text}"
    )

def frozen_candidates_from_scan(
    scan: pd.DataFrame,
    snapshot: dict,
) -> pd.DataFrame:
    """Return only candidates explicitly frozen before OOS reveal."""
    if scan is None or scan.empty or not snapshot:
        return pd.DataFrame()

    frozen = snapshot.get("candidates") or []
    if not frozen:
        return pd.DataFrame()

    rows = []
    for frozen_row in frozen:
        candidate_type = str(frozen_row.get("candidate_type", "STATE"))
        window = int(frozen_row.get("window_weeks", 0) or 0)
        upper = float(frozen_row.get("threshold_upper", np.nan))
        lower = float(frozen_row.get("threshold_lower", np.nan))
        feature = str(frozen_row.get("feature", "STATE"))
        q = frozen_row.get("flow_quantile", None)

        mask = (
            scan["candidate_type"].astype(str).eq(candidate_type)
            & _numeric(scan["window_weeks"]).eq(window)
            & _numeric(scan["threshold_upper"]).eq(upper)
            & _numeric(scan["threshold_lower"]).eq(lower)
        )

        if candidate_type == "FLOW":
            mask &= scan["feature"].astype(str).eq(feature)
            scan_q = _numeric(scan["flow_quantile"])
            if q is None or pd.isna(q):
                mask &= scan_q.isna()
            else:
                mask &= scan_q.eq(float(q))

        matches = scan.loc[mask].copy()
        if matches.empty:
            continue

        matches = matches.sort_values(
            ["rank_train_validation", "robustness_score"],
            ascending=[True, False],
        )
        chosen = matches.iloc[0].copy()
        chosen["frozen_order"] = len(rows) + 1
        rows.append(chosen)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("frozen_order").reset_index(drop=True)
