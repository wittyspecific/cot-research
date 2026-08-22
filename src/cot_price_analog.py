from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


REPORT_GROUPS = {
    "disaggregated": (
        ("producer", "Producer / Merchant", "COMMERCIAL / HEDGER"),
        ("managed_money", "Managed Money", "MOMENTUM / SPECULATIVE"),
        ("nonreportable", "Nonreportable", "RESIDUAL / CONTRARIAN"),
    ),
    "tff": (
        ("dealer", "Dealer / Intermediary", "INTERMEDIARY CONTEXT"),
        ("asset_manager", "Asset Manager", "INSTITUTIONAL"),
        ("leveraged_funds", "Leveraged Funds", "MOMENTUM / SPECULATIVE"),
        ("nonreportable", "Nonreportable", "RESIDUAL / CONTRARIAN"),
    ),
}

PRICE_FEATURES = (
    "price_return_4w",
    "price_return_8w",
    "price_return_13w",
    "price_return_26w",
    "price_drawdown_26w",
    "price_vs_ma13",
    "price_vs_ma26",
    "price_vol_13w",
)


def _finite(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices is None or len(prices) == 0:
        return pd.DataFrame()

    if isinstance(prices, pd.Series):
        prices = prices.to_frame("close")

    frame = prices.copy()
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame[~frame.index.isna()].sort_index()
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    frame = frame[~frame.index.duplicated(keep="last")]

    lookup = {
        str(col).strip().lower().replace(" ", "_"): col
        for col in frame.columns
    }

    close_col = next(
        (
            lookup[key]
            for key in ("close", "adj_close", "adjclose")
            if key in lookup
        ),
        None,
    )
    if close_col is None:
        return pd.DataFrame()

    high_col = lookup.get("high")
    low_col = lookup.get("low")

    out = pd.DataFrame(index=frame.index)
    out["close"] = pd.to_numeric(
        frame[close_col],
        errors="coerce",
    )
    out["high"] = (
        pd.to_numeric(frame[high_col], errors="coerce")
        if high_col is not None
        else out["close"]
    )
    out["low"] = (
        pd.to_numeric(frame[low_col], errors="coerce")
        if low_col is not None
        else out["close"]
    )

    out = out.dropna(subset=["close"])
    out["high"] = out["high"].fillna(out["close"])
    out["low"] = out["low"].fillna(out["close"])
    return out


def _rolling_percentile(
    series: pd.Series,
    *,
    window: int = 156,
    min_periods: int = 52,
) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").astype(float)

    def _rank(values):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if len(values) < int(min_periods):
            return np.nan
        current = values[-1]
        return float(
            100.0
            * np.mean(values <= current)
        )

    return x.rolling(
        int(window),
        min_periods=int(min_periods),
    ).apply(
        _rank,
        raw=True,
    )


def _price_asof_reports(
    prices: pd.DataFrame,
    availability_dates: pd.Series,
) -> pd.DataFrame:
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    # `load_prices()` may return a DatetimeIndex named e.g. "Date".
    # After reset_index() the first column therefore is not necessarily
    # literally called "index". Rename the actual first reset-index column
    # deterministically to `price_date`.
    right = p.reset_index()
    index_column = right.columns[0]

    right = (
        right.rename(
            columns={
                index_column: "price_date",
            }
        )
        .sort_values("price_date")
    )

    right["price_date"] = pd.to_datetime(
        right["price_date"],
        errors="coerce",
    )
    right = right.dropna(
        subset=["price_date"]
    )

    left = pd.DataFrame(
        {
            "availability_date": pd.to_datetime(
                availability_dates,
                errors="coerce",
            )
        }
    ).dropna(
        subset=["availability_date"]
    ).sort_values(
        "availability_date"
    )

    if left.empty or right.empty:
        return pd.DataFrame()

    merged = pd.merge_asof(
        left,
        right,
        left_on="availability_date",
        right_on="price_date",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged



def build_setup_frame(
    prices: pd.DataFrame,
    enriched_cot: pd.DataFrame,
    report_type: str,
    *,
    release_lag_days: int = 3,
) -> dict[str, Any]:
    """
    Build point-in-time-ish COT x Price snapshots.

    COT report_date is Tuesday positioning. We conservatively treat the data as
    available from report_date + 3 calendar days (normally Friday publication).
    All COT transformations use current/past reports only.
    """
    report_type = str(report_type)
    groups = REPORT_GROUPS.get(report_type, ())
    p = _clean_prices(prices)

    base = {
        "available": False,
        "report_type": report_type,
        "groups": [
            {
                "key": key,
                "label": label,
                "role": role,
            }
            for key, label, role in groups
        ],
        "frame": pd.DataFrame(),
        "price_features": list(PRICE_FEATURES),
        "cot_level_features": [],
        "cot_flow_features": [],
    }

    if p.empty or enriched_cot is None or enriched_cot.empty:
        return base

    x = enriched_cot.copy()
    required = {"report_date", "open_interest_all"}
    if not required.issubset(x.columns):
        return base

    x["report_date"] = pd.to_datetime(
        x["report_date"],
        errors="coerce",
    )
    x = (
        x.dropna(subset=["report_date"])
        .sort_values("report_date")
        .drop_duplicates("report_date", keep="last")
        .reset_index(drop=True)
    )
    if len(x) < 30:
        return base

    x["availability_date"] = (
        x["report_date"]
        + pd.to_timedelta(
            int(release_lag_days),
            unit="D",
        )
    )

    aligned = _price_asof_reports(
        p,
        x["availability_date"],
    )
    if aligned.empty:
        return base

    frame = pd.DataFrame(
        {
            "report_date": x["report_date"].values,
            "availability_date": x["availability_date"].values,
            "price_date": aligned["price_date"].values,
            "close": aligned["close"].values,
            "high": aligned["high"].values,
            "low": aligned["low"].values,
        }
    )

    close = pd.to_numeric(
        frame["close"],
        errors="coerce",
    )

    for weeks in (4, 8, 13, 26):
        frame[f"price_return_{weeks}w"] = (
            close.pct_change(
                weeks,
                fill_method=None,
            )
        )

    frame["price_drawdown_26w"] = (
        close
        / close.rolling(
            26,
            min_periods=13,
        ).max()
        - 1.0
    )
    frame["price_vs_ma13"] = (
        close
        / close.rolling(
            13,
            min_periods=8,
        ).mean()
        - 1.0
    )
    frame["price_vs_ma26"] = (
        close
        / close.rolling(
            26,
            min_periods=13,
        ).mean()
        - 1.0
    )
    logret = np.log(
        close
        / close.shift(1)
    )
    frame["price_vol_13w"] = (
        logret.rolling(
            13,
            min_periods=8,
        ).std(ddof=0)
        * np.sqrt(52.0)
    )

    oi = pd.to_numeric(
        x["open_interest_all"],
        errors="coerce",
    ).replace(0, np.nan)

    cot_level_features = []
    cot_flow_features = []
    available_groups = []

    for key, label, role in groups:
        long_col = f"{key}_long"
        short_col = f"{key}_short"
        if (
            long_col not in x.columns
            or short_col not in x.columns
        ):
            continue

        longs = pd.to_numeric(
            x[long_col],
            errors="coerce",
        )
        shorts = pd.to_numeric(
            x[short_col],
            errors="coerce",
        )

        net_oi = (
            longs - shorts
        ) / oi
        long_oi = longs / oi
        short_oi = shorts / oi

        frame[f"{key}_net_oi"] = net_oi.values
        frame[f"{key}_net_oi_percentile"] = (
            _rolling_percentile(
                net_oi,
                window=156,
                min_periods=52,
            ).values
        )

        cot_level_features.extend(
            [
                f"{key}_net_oi",
                f"{key}_net_oi_percentile",
            ]
        )

        for weeks in (1, 2, 4):
            name = f"{key}_net_oi_delta_{weeks}w"
            frame[name] = (
                net_oi.diff(weeks).values
            )
            cot_flow_features.append(name)

        frame[f"{key}_long_oi_delta_4w"] = (
            long_oi.diff(4).values
        )
        frame[f"{key}_short_oi_delta_4w"] = (
            short_oi.diff(4).values
        )
        cot_flow_features.extend(
            [
                f"{key}_long_oi_delta_4w",
                f"{key}_short_oi_delta_4w",
            ]
        )

        available_groups.append(
            {
                "key": key,
                "label": label,
                "role": role,
            }
        )

    frame = frame.dropna(
        subset=["availability_date", "close"]
    ).reset_index(drop=True)

    feature_cols = (
        list(PRICE_FEATURES)
        + cot_level_features
        + cot_flow_features
    )
    valid_features = [
        col
        for col in feature_cols
        if col in frame.columns
    ]

    if not valid_features:
        return base

    return {
        **base,
        "available": True,
        "groups": available_groups,
        "frame": frame,
        "price_features": [
            col
            for col in PRICE_FEATURES
            if col in frame.columns
        ],
        "cot_level_features": cot_level_features,
        "cot_flow_features": cot_flow_features,
    }


def _robust_scale(
    frame: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.Series, pd.Series]:
    values = frame[columns].apply(
        pd.to_numeric,
        errors="coerce",
    )
    median = values.median(axis=0)
    mad = (
        values.sub(median, axis=1)
        .abs()
        .median(axis=0)
    )
    robust_sigma = (
        mad / 0.6744897501960817
    )
    std = values.std(axis=0, ddof=0)
    scale = robust_sigma.where(
        robust_sigma > 1e-9,
        std,
    )
    scale = scale.where(
        scale > 1e-9,
        1.0,
    )
    return median, scale


def _component_similarity(
    current: pd.Series,
    candidates: pd.DataFrame,
    columns: list[str],
    reference: pd.DataFrame,
) -> pd.Series:
    cols = [
        col
        for col in columns
        if (
            col in candidates.columns
            and col in current.index
        )
    ]
    if not cols:
        return pd.Series(
            np.nan,
            index=candidates.index,
            dtype=float,
        )

    median, scale = _robust_scale(
        reference,
        cols,
    )
    current_z = (
        pd.to_numeric(
            current[cols],
            errors="coerce",
        )
        - median
    ) / scale

    candidate_z = (
        candidates[cols].apply(
            pd.to_numeric,
            errors="coerce",
        )
        - median
    ).div(
        scale,
        axis=1,
    )

    diff = candidate_z.sub(
        current_z,
        axis=1,
    )

    available = diff.notna().sum(axis=1)
    mse = (
        diff.pow(2)
        .sum(axis=1, skipna=True)
        .div(
            available.replace(0, np.nan)
        )
    )
    rmse = np.sqrt(
        mse.clip(lower=0.0)
    )

    similarity = (
        100.0
        * np.exp(
            -0.5
            * rmse.pow(2)
        )
    )

    minimum = max(
        2,
        int(
            np.ceil(
                len(cols) * 0.50
            )
        ),
    )
    similarity = similarity.where(
        available >= minimum
    )
    return similarity.clip(
        0.0,
        100.0,
    )


def _future_price(
    prices: pd.DataFrame,
    target: pd.Timestamp,
) -> float:
    p = _clean_prices(prices)
    if p.empty:
        return np.nan

    pos = p.index.searchsorted(
        pd.Timestamp(target),
        side="left",
    )
    if pos >= len(p):
        return np.nan
    return _finite(
        p.iloc[int(pos)]["close"]
    )


def _entry_price(
    prices: pd.DataFrame,
    anchor: pd.Timestamp,
) -> tuple[pd.Timestamp | None, float]:
    p = _clean_prices(prices)
    if p.empty:
        return None, np.nan

    pos = p.index.searchsorted(
        pd.Timestamp(anchor),
        side="right",
    ) - 1
    if pos < 0:
        return None, np.nan

    date = pd.Timestamp(
        p.index[int(pos)]
    )
    return date, _finite(
        p.iloc[int(pos)]["close"]
    )


def forward_outcome(
    prices: pd.DataFrame,
    anchor: pd.Timestamp,
    *,
    horizons_weeks: tuple[int, ...] = (2, 4, 8, 12),
    excursion_horizon_weeks: int = 8,
) -> dict[str, Any]:
    p = _clean_prices(prices)
    entry_date, entry = _entry_price(
        p,
        pd.Timestamp(anchor),
    )

    out = {
        "entry_price_date": entry_date,
        "entry_price": entry,
    }

    if entry_date is None or not np.isfinite(entry) or entry <= 0:
        for weeks in horizons_weeks:
            out[f"return_{weeks}w"] = np.nan
        out["mae"] = np.nan
        out["mfe"] = np.nan
        return out

    for weeks in horizons_weeks:
        future = _future_price(
            p,
            entry_date
            + pd.Timedelta(
                weeks=int(weeks)
            ),
        )
        out[f"return_{weeks}w"] = (
            future / entry - 1.0
            if np.isfinite(future)
            else np.nan
        )

    end = (
        entry_date
        + pd.Timedelta(
            weeks=int(
                excursion_horizon_weeks
            )
        )
    )
    path = p.loc[
        (p.index > entry_date)
        & (p.index <= end)
    ]
    if path.empty:
        out["mae"] = np.nan
        out["mfe"] = np.nan
    else:
        out["mae"] = float(
            path["low"].min()
            / entry
            - 1.0
        )
        out["mfe"] = float(
            path["high"].max()
            / entry
            - 1.0
        )

    return out


def _spaced_top_matches(
    ranked: pd.DataFrame,
    *,
    top_n: int,
    min_spacing_weeks: int,
) -> pd.DataFrame:
    if ranked.empty:
        return ranked

    selected = []
    selected_dates = []

    for idx, row in ranked.iterrows():
        date = pd.Timestamp(
            row["availability_date"]
        )

        if all(
            abs(
                (
                    date - other
                ).days
            )
            >= int(
                min_spacing_weeks
            ) * 7
            for other in selected_dates
        ):
            selected.append(idx)
            selected_dates.append(date)

        if len(selected) >= int(top_n):
            break

    return ranked.loc[selected].copy()


def analyze_historical_analogs(
    prices: pd.DataFrame,
    enriched_cot: pd.DataFrame,
    report_type: str,
    *,
    top_n: int = 8,
    min_spacing_weeks: int = 13,
    exclude_recent_weeks: int = 26,
    excursion_horizon_weeks: int = 8,
) -> dict[str, Any]:
    setup = build_setup_frame(
        prices,
        enriched_cot,
        report_type,
    )

    empty = {
        "available": False,
        "reason": "Nicht genügend gemeinsame Preis-/COT-Historie.",
        "report_type": str(report_type),
        "groups": setup.get("groups", []),
        "matches": pd.DataFrame(),
        "aggregate": {},
        "current": {},
    }

    if not setup.get("available"):
        return empty

    frame = setup["frame"].copy()
    all_features = (
        setup["price_features"]
        + setup["cot_level_features"]
        + setup["cot_flow_features"]
    )

    complete_count = (
        frame[all_features]
        .notna()
        .sum(axis=1)
    )
    minimum_features = max(
        5,
        int(
            np.ceil(
                len(all_features)
                * 0.55
            )
        ),
    )
    valid = frame.loc[
        complete_count >= minimum_features
    ].copy()

    if len(valid) < 20:
        return {
            **empty,
            "reason": (
                "Zu wenig historische Snapshots mit ausreichend vollständigen "
                "Preis- und COT-Features."
            ),
        }

    current = valid.iloc[-1].copy()
    current_date = pd.Timestamp(
        current["availability_date"]
    )

    candidate_cutoff = (
        current_date
        - pd.Timedelta(
            weeks=max(
                int(exclude_recent_weeks),
                int(excursion_horizon_weeks) + 2,
            )
        )
    )
    candidates = valid.loc[
        pd.to_datetime(
            valid["availability_date"]
        ) <= candidate_cutoff
    ].copy()

    if len(candidates) < int(top_n):
        return {
            **empty,
            "reason": (
                "Nicht genügend voneinander getrennte historische Kandidaten "
                "vor dem aktuellen Setup."
            ),
        }

    reference = valid.loc[
        pd.to_datetime(
            valid["availability_date"]
        ) <= current_date
    ].copy()

    candidates["price_similarity"] = _component_similarity(
        current,
        candidates,
        setup["price_features"],
        reference,
    )
    candidates["cot_level_similarity"] = _component_similarity(
        current,
        candidates,
        setup["cot_level_features"],
        reference,
    )
    candidates["cot_flow_similarity"] = _component_similarity(
        current,
        candidates,
        setup["cot_flow_features"],
        reference,
    )

    components = pd.DataFrame(
        {
            "price": candidates["price_similarity"],
            "level": candidates["cot_level_similarity"],
            "flow": candidates["cot_flow_similarity"],
        },
        index=candidates.index,
    )
    weights = pd.Series(
        {
            "price": 0.50,
            "level": 0.25,
            "flow": 0.25,
        }
    )

    weighted = components.mul(
        weights,
        axis=1,
    )
    denom = components.notna().mul(
        weights,
        axis=1,
    ).sum(axis=1)

    candidates["similarity"] = (
        weighted.sum(
            axis=1,
            skipna=True,
        )
        / denom.replace(0.0, np.nan)
    )

    ranked = candidates.dropna(
        subset=["similarity"]
    ).sort_values(
        "similarity",
        ascending=False,
    )

    matches = _spaced_top_matches(
        ranked,
        top_n=int(top_n),
        min_spacing_weeks=int(
            min_spacing_weeks
        ),
    )

    outcome_rows = []
    for idx, row in matches.iterrows():
        outcome = forward_outcome(
            prices,
            pd.Timestamp(
                row["availability_date"]
            ),
            excursion_horizon_weeks=int(
                excursion_horizon_weeks
            ),
        )
        outcome_rows.append(
            {
                "_idx": idx,
                **outcome,
            }
        )

    if outcome_rows:
        outcome_frame = (
            pd.DataFrame(outcome_rows)
            .set_index("_idx")
        )
        for col in outcome_frame.columns:
            matches[col] = outcome_frame[
                col
            ]

    matches = matches.reset_index(
        drop=True
    )

    aggregate = {
        "matches": int(len(matches)),
        "median_similarity": np.nan,
        "median_price_similarity": np.nan,
        "median_cot_level_similarity": np.nan,
        "median_cot_flow_similarity": np.nan,
        "median_mae": np.nan,
        "median_mfe": np.nan,
    }

    if not matches.empty:
        aggregate.update(
            {
                "median_similarity": float(
                    pd.to_numeric(
                        matches["similarity"],
                        errors="coerce",
                    ).median()
                ),
                "median_price_similarity": float(
                    pd.to_numeric(
                        matches["price_similarity"],
                        errors="coerce",
                    ).median()
                ),
                "median_cot_level_similarity": float(
                    pd.to_numeric(
                        matches["cot_level_similarity"],
                        errors="coerce",
                    ).median()
                ),
                "median_cot_flow_similarity": float(
                    pd.to_numeric(
                        matches["cot_flow_similarity"],
                        errors="coerce",
                    ).median()
                ),
                "median_mae": float(
                    pd.to_numeric(
                        matches.get("mae"),
                        errors="coerce",
                    ).median()
                ),
                "median_mfe": float(
                    pd.to_numeric(
                        matches.get("mfe"),
                        errors="coerce",
                    ).median()
                ),
            }
        )

        for weeks in (2, 4, 8, 12):
            col = f"return_{weeks}w"
            values = pd.to_numeric(
                matches.get(col),
                errors="coerce",
            ).dropna()

            aggregate[f"n_{weeks}w"] = int(
                len(values)
            )
            aggregate[f"positive_rate_{weeks}w"] = (
                float(
                    (values > 0).mean()
                )
                if len(values)
                else np.nan
            )
            aggregate[f"median_return_{weeks}w"] = (
                float(values.median())
                if len(values)
                else np.nan
            )

    horizon = int(
        excursion_horizon_weeks
    )
    hit = _finite(
        aggregate.get(
            f"positive_rate_{horizon}w"
        )
    )
    median_return = _finite(
        aggregate.get(
            f"median_return_{horizon}w"
        )
    )

    if (
        np.isfinite(hit)
        and np.isfinite(median_return)
        and hit >= 0.60
        and median_return > 0
    ):
        outcome_bias = "BULLISH"
    elif (
        np.isfinite(hit)
        and np.isfinite(median_return)
        and hit <= 0.40
        and median_return < 0
    ):
        outcome_bias = "BEARISH"
    else:
        outcome_bias = "MIXED"

    n = int(
        aggregate.get("matches", 0)
    )
    if n < 6:
        sample_quality = "SMALL SAMPLE"
    elif n < 12:
        sample_quality = "LIMITED SAMPLE"
    else:
        sample_quality = "BROADER SAMPLE"

    aggregate["outcome_horizon_weeks"] = horizon
    aggregate["outcome_bias"] = outcome_bias
    aggregate["sample_quality"] = sample_quality

    group_snapshot = []
    for group in setup["groups"]:
        key = group["key"]
        group_snapshot.append(
            {
                **group,
                "net_oi": _finite(
                    current.get(
                        f"{key}_net_oi"
                    )
                ),
                "percentile": _finite(
                    current.get(
                        f"{key}_net_oi_percentile"
                    )
                ),
                "delta_1w": _finite(
                    current.get(
                        f"{key}_net_oi_delta_1w"
                    )
                ),
                "delta_2w": _finite(
                    current.get(
                        f"{key}_net_oi_delta_2w"
                    )
                ),
                "delta_4w": _finite(
                    current.get(
                        f"{key}_net_oi_delta_4w"
                    )
                ),
                "long_delta_4w": _finite(
                    current.get(
                        f"{key}_long_oi_delta_4w"
                    )
                ),
                "short_delta_4w": _finite(
                    current.get(
                        f"{key}_short_oi_delta_4w"
                    )
                ),
            }
        )

    current_summary = {
        "report_date": pd.Timestamp(
            current["report_date"]
        ),
        "availability_date": current_date,
        "price_date": pd.Timestamp(
            current["price_date"]
        ),
        "close": _finite(
            current["close"]
        ),
        "price_return_4w": _finite(
            current.get(
                "price_return_4w"
            )
        ),
        "price_return_8w": _finite(
            current.get(
                "price_return_8w"
            )
        ),
        "price_return_13w": _finite(
            current.get(
                "price_return_13w"
            )
        ),
        "price_drawdown_26w": _finite(
            current.get(
                "price_drawdown_26w"
            )
        ),
        "price_vs_ma26": _finite(
            current.get(
                "price_vs_ma26"
            )
        ),
        "price_vol_13w": _finite(
            current.get(
                "price_vol_13w"
            )
        ),
        "groups": group_snapshot,
    }

    return {
        "available": bool(
            not matches.empty
        ),
        "reason": "",
        "report_type": str(report_type),
        "groups": setup["groups"],
        "matches": matches,
        "aggregate": aggregate,
        "current": current_summary,
        "method": {
            "price_weight": 0.50,
            "cot_level_weight": 0.25,
            "cot_flow_weight": 0.25,
            "min_spacing_weeks": int(
                min_spacing_weeks
            ),
            "exclude_recent_weeks": int(
                exclude_recent_weeks
            ),
            "cot_release_lag_days": 3,
        },
    }


def normalized_analog_paths(
    prices: pd.DataFrame,
    *,
    current_anchor: pd.Timestamp,
    historical_anchors: list[pd.Timestamp],
    lookback_weeks: int = 13,
    forward_weeks: int = 8,
) -> pd.DataFrame:
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    rows = []

    anchors = [
        ("CURRENT", pd.Timestamp(current_anchor), True)
    ]
    anchors.extend(
        (
            pd.Timestamp(anchor).date().isoformat(),
            pd.Timestamp(anchor),
            False,
        )
        for anchor in historical_anchors
    )

    for label, anchor, is_current in anchors:
        start = (
            anchor
            - pd.Timedelta(
                weeks=int(
                    lookback_weeks
                )
            )
        )
        end = (
            anchor
            if is_current
            else anchor
            + pd.Timedelta(
                weeks=int(
                    forward_weeks
                )
            )
        )

        sample = p.loc[
            (p.index >= start)
            & (p.index <= end),
            ["close"],
        ].copy()

        if sample.empty:
            continue

        entry_date, entry = _entry_price(
            p,
            anchor,
        )
        if (
            entry_date is None
            or not np.isfinite(entry)
            or entry <= 0
        ):
            continue

        sample["relative_day"] = (
            sample.index
            - entry_date
        ).days
        sample["normalized"] = (
            sample["close"]
            / entry
            * 100.0
        )
        sample["analog"] = label
        rows.append(
            sample[
                [
                    "relative_day",
                    "normalized",
                    "analog",
                ]
            ]
        )

    if not rows:
        return pd.DataFrame()

    return pd.concat(
        rows,
        axis=0,
        ignore_index=True,
    )
