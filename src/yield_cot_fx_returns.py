from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .fx_relative import load_currency_usd_values, synthesize_pair_prices
from .rates_cot_ml import (
    RATES_INFORMATION_LAG_BDAYS,
    PURGE_WEEKS,
    _clean_rate_series,
    _load_cot_state_histories,
)
from .yield_spreads import fetch_yield_universe, spread_series


# V3.19.0 · YIELD X COT → FX RETURNS
#
# New research question:
#   Do COT positioning and historically-normalized 2Y-rate repricing contain
#   useful information for subsequent FX returns?
#
# This deliberately replaces the causal assumption "Rates must predict COT"
# with a direct market target.
#
# Research safety:
#   - state-change episodes, not every overlapping week
#   - publication-aware COT state histories
#   - additional 5-business-day rates safety lag
#   - current rates move excluded from its own historical reference
#   - yearly walk-forward with 8-week purge
#   - feature ablation: COT only / Rates only / COT + Rates
#   - no production signal, risk, journal or execution mutation

PAIR_CURRENCY_ORDER = (
    "EUR",
    "GBP",
    "AUD",
    "NZD",
    "USD",
    "CAD",
    "JPY",
)
RATES_HORIZONS = (5, 20, 60)
RETURN_HORIZONS = (1, 4, 8)
MEANINGFUL_PERCENTILE = 75.0
NORMALIZATION_LOOKBACK_YEARS = 5
NORMALIZATION_MIN_HISTORY = 252
MIN_TRAIN_ROWS_FX = 120
MIN_TEST_ROWS_FX = 12

PHASE_CODE_FX = {
    "NEUTRAL": 0,
    "EXTREME": 1,
    "TRANSITION": 2,
    "RELEASE": 3,
}

COT_FEATURES_FX = [
    "cot_pair_score",
    "cot_pair_direction",
    "cot_pair_strength",
    "base_phase_code",
    "quote_phase_code",
    "base_active",
    "quote_active",
    "commercial_percentile_diff",
    "base_cot_delta_1w",
    "quote_cot_delta_1w",
    "base_cot_delta_4w",
    "quote_cot_delta_4w",
    "base_distance_from_extreme",
    "quote_distance_from_extreme",
]

RATES_FEATURES_FX = [
    "rates_level_bp",
    "rates5_delta_bp",
    "rates5_percentile",
    "rates5_direction",
    "rates20_delta_bp",
    "rates20_percentile",
    "rates20_direction",
    "rates60_delta_bp",
    "rates60_percentile",
    "rates60_direction",
    "rates_alignment_count",
]

COMBINED_FEATURES_FX = list(
    dict.fromkeys(
        COT_FEATURES_FX
        + RATES_FEATURES_FX
        + ["cot_rates_alignment"]
    )
)


def _finite(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if np.isfinite(x) else default


def _naive_ts(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts


def _sign(value: Any) -> int:
    x = _finite(value, 0.0)
    return 1 if x > 0 else -1 if x < 0 else 0


def _phase_code(value: Any) -> int:
    return int(
        PHASE_CODE_FX.get(
            str(value or "NEUTRAL").upper(),
            0,
        )
    )


def _move_arrays(
    spread: pd.Series,
    periods: int,
) -> tuple[np.ndarray, np.ndarray]:
    clean = pd.Series(spread).dropna().sort_index()
    if len(clean) <= int(periods):
        return (
            np.asarray([], dtype="datetime64[ns]"),
            np.asarray([], dtype=float),
        )

    moves = (
        clean.diff(int(periods)) * 100.0
    ).dropna()
    if moves.empty:
        return (
            np.asarray([], dtype="datetime64[ns]"),
            np.asarray([], dtype=float),
        )

    return (
        moves.index.to_numpy(dtype="datetime64[ns]"),
        moves.to_numpy(dtype=float),
    )


def _historical_move_lookup(
    move_dates: np.ndarray,
    move_values: np.ndarray,
    asof_date,
) -> dict[str, Any]:
    if len(move_dates) == 0:
        return {
            "delta_bp": np.nan,
            "percentile": np.nan,
            "history_count": 0,
        }

    asof = _naive_ts(asof_date)
    cutoff_np = np.datetime64(asof.to_datetime64())
    pos = int(
        np.searchsorted(
            move_dates,
            cutoff_np,
            side="right",
        )
        - 1
    )
    if pos < 0:
        return {
            "delta_bp": np.nan,
            "percentile": np.nan,
            "history_count": 0,
        }

    current_move = float(move_values[pos])
    current_date = _naive_ts(move_dates[pos])
    history_values = move_values[:pos]
    history_dates = move_dates[:pos]

    history_cutoff = (
        current_date
        - pd.DateOffset(
            years=NORMALIZATION_LOOKBACK_YEARS
        )
    )
    history_cutoff_np = np.datetime64(
        history_cutoff.to_datetime64()
    )
    recent_start = int(
        np.searchsorted(
            history_dates,
            history_cutoff_np,
            side="left",
        )
    )

    recent = history_values[recent_start:]
    recent = recent[np.isfinite(recent)]
    full = history_values[np.isfinite(history_values)]

    if len(recent) >= NORMALIZATION_MIN_HISTORY:
        sample = recent
    elif len(full) >= NORMALIZATION_MIN_HISTORY:
        sample = full
    else:
        return {
            "delta_bp": current_move,
            "percentile": np.nan,
            "history_count": int(len(recent)),
        }

    hist_abs = np.abs(sample)
    current_abs = abs(current_move)
    less = int(np.sum(hist_abs < current_abs))
    equal = int(np.sum(hist_abs == current_abs))
    percentile = (
        100.0
        * (less + 0.5 * equal)
        / float(len(hist_abs))
    )

    return {
        "delta_bp": current_move,
        "percentile": float(
            max(0.0, min(100.0, percentile))
        ),
        "history_count": int(len(hist_abs)),
    }


def _spread_level_asof(
    spread: pd.Series,
    asof_date,
) -> float:
    clean = pd.Series(spread).dropna().sort_index()
    if clean.empty:
        return np.nan

    idx = clean.index.to_numpy(
        dtype="datetime64[ns]"
    )
    values = clean.to_numpy(dtype=float)
    cutoff = np.datetime64(
        _naive_ts(asof_date).to_datetime64()
    )
    pos = int(
        np.searchsorted(
            idx,
            cutoff,
            side="right",
        )
        - 1
    )
    if pos < 0:
        return np.nan

    # Underlying yield series are percentage points; convert spread to bp.
    return float(values[pos] * 100.0)


def _rates_direction(
    delta_bp: Any,
    percentile: Any,
) -> int:
    delta = _finite(delta_bp)
    pctl = _finite(percentile)
    if (
        not np.isfinite(delta)
        or not np.isfinite(pctl)
        or pctl < MEANINGFUL_PERCENTILE
    ):
        return 0
    return _sign(delta)


def classify_pair_state(
    cot_direction: int,
    rates_direction: int,
) -> str:
    cot = int(np.sign(int(cot_direction or 0)))
    rates = int(np.sign(int(rates_direction or 0)))

    if cot != 0 and rates != 0:
        return (
            "ALIGNED"
            if cot == rates
            else "CONFLICT"
        )
    if cot != 0:
        return "COT_ONLY"
    if rates != 0:
        return "RATES_ONLY"
    return "NEUTRAL"


def _cot_pair_rows(
    base_history: pd.DataFrame,
    quote_history: pd.DataFrame,
) -> pd.DataFrame:
    if (
        base_history is None
        or quote_history is None
        or base_history.empty
        or quote_history.empty
    ):
        return pd.DataFrame()

    base_cols = {
        "cot_phase": "base_cot_phase",
        "cot_direction": "base_cot_direction",
        "cot_active": "base_active",
        "commercial_percentile": "base_commercial_percentile",
        "cot_delta_1w": "base_cot_delta_1w",
        "cot_delta_2w": "base_cot_delta_2w",
        "cot_delta_4w": "base_cot_delta_4w",
        "distance_from_extreme": "base_distance_from_extreme",
    }
    quote_cols = {
        "cot_phase": "quote_cot_phase",
        "cot_direction": "quote_cot_direction",
        "cot_active": "quote_active",
        "commercial_percentile": "quote_commercial_percentile",
        "cot_delta_1w": "quote_cot_delta_1w",
        "cot_delta_2w": "quote_cot_delta_2w",
        "cot_delta_4w": "quote_cot_delta_4w",
        "distance_from_extreme": "quote_distance_from_extreme",
    }

    b = (
        base_history[
            ["available_date"] + list(base_cols)
        ]
        .rename(columns=base_cols)
        .sort_values("available_date")
    )
    q = (
        quote_history[
            ["available_date"] + list(quote_cols)
        ]
        .rename(columns=quote_cols)
        .sort_values("available_date")
    )

    merged = pd.merge_asof(
        b,
        q,
        on="available_date",
        direction="backward",
        tolerance=pd.Timedelta(days=8),
    )
    merged = merged.dropna(
        subset=[
            "base_cot_direction",
            "quote_cot_direction",
        ]
    ).copy()

    return merged


def _forward_return_after(
    prices: pd.DataFrame,
    asof_date,
    horizon_weeks: int,
) -> dict[str, Any]:
    if (
        prices is None
        or prices.empty
        or "close" not in prices.columns
    ):
        return {
            "trade_date": pd.NaT,
            "exit_date": pd.NaT,
            "return": np.nan,
        }

    frame = prices[["close"]].copy()
    frame.index = pd.to_datetime(
        frame.index,
        errors="coerce",
    )
    frame["close"] = pd.to_numeric(
        frame["close"],
        errors="coerce",
    )
    frame = (
        frame[~frame.index.isna()]
        .dropna()
        .sort_index()
    )
    if frame.empty:
        return {
            "trade_date": pd.NaT,
            "exit_date": pd.NaT,
            "return": np.nan,
        }

    dates = frame.index.to_numpy(
        dtype="datetime64[ns]"
    )
    close = frame["close"].to_numpy(dtype=float)

    signal_ts = np.datetime64(
        _naive_ts(asof_date).to_datetime64()
    )
    entry_pos = int(
        np.searchsorted(
            dates,
            signal_ts,
            side="right",
        )
    )
    if entry_pos >= len(dates):
        return {
            "trade_date": pd.NaT,
            "exit_date": pd.NaT,
            "return": np.nan,
        }

    entry_date = _naive_ts(dates[entry_pos])
    entry = float(close[entry_pos])
    if not np.isfinite(entry) or entry <= 0:
        return {
            "trade_date": pd.NaT,
            "exit_date": pd.NaT,
            "return": np.nan,
        }

    target = (
        entry_date
        + pd.Timedelta(
            weeks=int(horizon_weeks)
        )
    )
    target_np = np.datetime64(
        target.to_datetime64()
    )
    exit_pos = int(
        np.searchsorted(
            dates,
            target_np,
            side="left",
        )
    )
    if exit_pos >= len(dates):
        return {
            "trade_date": entry_date,
            "exit_date": pd.NaT,
            "return": np.nan,
        }

    exit_price = float(close[exit_pos])
    if (
        not np.isfinite(exit_price)
        or exit_price <= 0
    ):
        return {
            "trade_date": entry_date,
            "exit_date": _naive_ts(
                dates[exit_pos]
            ),
            "return": np.nan,
        }

    return {
        "trade_date": entry_date,
        "exit_date": _naive_ts(
            dates[exit_pos]
        ),
        "return": float(
            exit_price / entry - 1.0
        ),
    }


def _build_pair_weekly_states(
    cot_histories: Mapping[str, pd.DataFrame],
    yield_universe: Mapping[str, Any],
    fx_values: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    available = [
        currency
        for currency in PAIR_CURRENCY_ORDER
        if (
            currency in cot_histories
            and currency in yield_universe
            and currency in fx_values
            and not _clean_rate_series(
                yield_universe[currency]
            ).empty
        )
    ]

    errors: list[dict[str, str]] = []
    rows = []

    for base, quote in combinations(
        available,
        2,
    ):
        pair = f"{base}{quote}"

        try:
            cot = _cot_pair_rows(
                cot_histories[base],
                cot_histories[quote],
            )
            if cot.empty:
                raise RuntimeError(
                    "Keine gemeinsame COT-Historie."
                )

            spread = spread_series(
                _clean_rate_series(
                    yield_universe[base]
                ),
                _clean_rate_series(
                    yield_universe[quote]
                ),
                name=pair,
            )
            if spread.empty:
                raise RuntimeError(
                    "Keine gemeinsame 2Y-Spread-Historie."
                )

            move_cache = {
                horizon: _move_arrays(
                    spread,
                    horizon,
                )
                for horizon in RATES_HORIZONS
            }

            for _, row in cot.iterrows():
                asof = _naive_ts(
                    row["available_date"]
                )
                rates_cutoff = (
                    asof
                    - pd.offsets.BDay(
                        RATES_INFORMATION_LAG_BDAYS
                    )
                )

                stats = {}
                for horizon in RATES_HORIZONS:
                    move_dates, move_values = (
                        move_cache[horizon]
                    )
                    stats[horizon] = (
                        _historical_move_lookup(
                            move_dates,
                            move_values,
                            rates_cutoff,
                        )
                    )

                rates_dirs = {
                    horizon: _rates_direction(
                        stats[horizon][
                            "delta_bp"
                        ],
                        stats[horizon][
                            "percentile"
                        ],
                    )
                    for horizon in RATES_HORIZONS
                }

                base_dir = _sign(
                    row["base_cot_direction"]
                )
                quote_dir = _sign(
                    row["quote_cot_direction"]
                )
                cot_score = (
                    base_dir - quote_dir
                )
                cot_direction = _sign(
                    cot_score
                )
                rates20_direction = int(
                    rates_dirs[20]
                )
                relation = classify_pair_state(
                    cot_direction,
                    rates20_direction,
                )

                rates_alignment_count = (
                    sum(
                        int(rates_dirs[h])
                        == rates20_direction
                        and rates20_direction != 0
                        for h in RATES_HORIZONS
                    )
                )
                cot_rates_alignment = (
                    1
                    if (
                        cot_direction != 0
                        and cot_direction
                        == rates20_direction
                    )
                    else -1
                    if (
                        cot_direction != 0
                        and rates20_direction != 0
                        and cot_direction
                        == -rates20_direction
                    )
                    else 0
                )

                rows.append(
                    {
                        "pair": pair,
                        "base": base,
                        "quote": quote,
                        "available_date": asof,
                        "rates_cutoff": rates_cutoff,
                        "relation": relation,
                        "cot_pair_score": float(
                            cot_score
                        ),
                        "cot_pair_direction": int(
                            cot_direction
                        ),
                        "base_cot_direction": int(base_dir),
                        "quote_cot_direction": int(quote_dir),
                        "cot_pair_strength": abs(
                            float(cot_score)
                        ),
                        "base_phase_code": _phase_code(
                            row["base_cot_phase"]
                        ),
                        "quote_phase_code": _phase_code(
                            row["quote_cot_phase"]
                        ),
                        "base_cot_phase": str(
                            row["base_cot_phase"]
                        ),
                        "quote_cot_phase": str(
                            row["quote_cot_phase"]
                        ),
                        "base_active": int(
                            bool(
                                row["base_active"]
                            )
                        ),
                        "quote_active": int(
                            bool(
                                row["quote_active"]
                            )
                        ),
                        "commercial_percentile_diff": (
                            _finite(
                                row[
                                    "base_commercial_percentile"
                                ]
                            )
                            - _finite(
                                row[
                                    "quote_commercial_percentile"
                                ]
                            )
                        ),
                        "base_cot_delta_1w": _finite(
                            row["base_cot_delta_1w"]
                        ),
                        "quote_cot_delta_1w": _finite(
                            row["quote_cot_delta_1w"]
                        ),
                        "base_cot_delta_4w": _finite(
                            row["base_cot_delta_4w"]
                        ),
                        "quote_cot_delta_4w": _finite(
                            row["quote_cot_delta_4w"]
                        ),
                        "base_distance_from_extreme": _finite(
                            row[
                                "base_distance_from_extreme"
                            ]
                        ),
                        "quote_distance_from_extreme": _finite(
                            row[
                                "quote_distance_from_extreme"
                            ]
                        ),
                        "rates_level_bp": _spread_level_asof(
                            spread,
                            rates_cutoff,
                        ),
                        "rates5_delta_bp": _finite(
                            stats[5]["delta_bp"]
                        ),
                        "rates5_percentile": _finite(
                            stats[5]["percentile"]
                        ),
                        "rates5_direction": int(
                            rates_dirs[5]
                        ),
                        "rates20_delta_bp": _finite(
                            stats[20]["delta_bp"]
                        ),
                        "rates20_percentile": _finite(
                            stats[20]["percentile"]
                        ),
                        "rates20_direction": int(
                            rates20_direction
                        ),
                        "rates60_delta_bp": _finite(
                            stats[60]["delta_bp"]
                        ),
                        "rates60_percentile": _finite(
                            stats[60]["percentile"]
                        ),
                        "rates60_direction": int(
                            rates_dirs[60]
                        ),
                        "rates_alignment_count": int(
                            rates_alignment_count
                        ),
                        "cot_rates_alignment": int(
                            cot_rates_alignment
                        ),
                    }
                )

        except Exception as exc:
            errors.append(
                {
                    "pair": pair,
                    "stage": "STATE BUILD",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    weekly = pd.DataFrame(rows)
    if weekly.empty:
        return weekly, errors

    weekly = weekly.sort_values(
        ["pair", "available_date"]
    ).reset_index(drop=True)

    episode_start = pd.Series(
        False,
        index=weekly.index,
    )
    for _, group in weekly.groupby(
        "pair",
        sort=False,
    ):
        previous_date = None
        previous_state = None

        for idx in group.index:
            row = weekly.loc[idx]
            state = (
                int(
                    row[
                        "cot_pair_direction"
                    ]
                ),
                int(
                    row[
                        "rates20_direction"
                    ]
                ),
                str(row["relation"]),
            )
            date = _naive_ts(
                row["available_date"]
            )

            new_episode = (
                previous_date is None
                or (
                    date - previous_date
                ).days > 10
                or state != previous_state
            )
            episode_start.loc[idx] = bool(
                new_episode
            )
            previous_date = date
            previous_state = state

    weekly["episode_start"] = (
        episode_start.astype(bool)
    )
    return weekly, errors


def _attach_fx_returns(
    events: pd.DataFrame,
    fx_values: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    if events is None or events.empty:
        return (
            pd.DataFrame()
            if events is None
            else events.copy()
        )

    out = events.copy()

    for horizon in RETURN_HORIZONS:
        out[f"return_{horizon}w"] = np.nan
        out[f"positive_{horizon}w"] = np.nan

    for pair, group in out.groupby(
        "pair",
        sort=False,
    ):
        first = group.iloc[0]
        prices = synthesize_pair_prices(
            str(first["base"]),
            str(first["quote"]),
            dict(fx_values),
        )
        if prices.empty:
            continue

        for idx in group.index:
            asof = out.loc[
                idx,
                "available_date",
            ]
            for horizon in RETURN_HORIZONS:
                result = _forward_return_after(
                    prices,
                    asof,
                    horizon,
                )
                ret = _finite(
                    result["return"]
                )
                if np.isfinite(ret):
                    out.loc[
                        idx,
                        f"return_{horizon}w",
                    ] = ret
                    out.loc[
                        idx,
                        f"positive_{horizon}w",
                    ] = float(ret > 0)

    return out


def _state_direction(
    relation: str,
    cot_direction: int,
    rates_direction: int,
    *,
    conflict_source: str = "COT",
) -> int:
    relation = str(relation)

    if relation == "ALIGNED":
        return int(cot_direction)
    if relation == "COT_ONLY":
        return int(cot_direction)
    if relation == "RATES_ONLY":
        return int(rates_direction)
    if relation == "CONFLICT":
        return (
            int(cot_direction)
            if str(conflict_source).upper()
            == "COT"
            else int(rates_direction)
        )
    return 0


def _baseline_table(
    events: pd.DataFrame,
) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()

    specs = [
        ("ALIGNED", "ALIGNED", "COT"),
        ("COT ONLY", "COT_ONLY", "COT"),
        ("RATES ONLY", "RATES_ONLY", "RATES"),
        (
            "CONFLICT · follow COT",
            "CONFLICT",
            "COT",
        ),
        (
            "CONFLICT · follow Rates",
            "CONFLICT",
            "RATES",
        ),
    ]

    rows = []
    for label, relation, source in specs:
        subset = events[
            events["relation"].eq(
                relation
            )
        ].copy()
        if subset.empty:
            continue

        directions = subset.apply(
            lambda row: _state_direction(
                str(row["relation"]),
                int(
                    row[
                        "cot_pair_direction"
                    ]
                ),
                int(
                    row[
                        "rates20_direction"
                    ]
                ),
                conflict_source=source,
            ),
            axis=1,
        ).astype(int)

        for horizon in RETURN_HORIZONS:
            raw = pd.to_numeric(
                subset[
                    f"return_{horizon}w"
                ],
                errors="coerce",
            )
            aligned = (
                raw
                * directions.to_numpy(
                    dtype=float
                )
            )
            aligned = pd.Series(
                aligned,
                index=subset.index,
            ).dropna()
            aligned = aligned[
                np.isfinite(aligned)
            ]

            if aligned.empty:
                continue

            rows.append(
                {
                    "State": label,
                    "Horizont": f"{horizon}W",
                    "n": int(len(aligned)),
                    "Hit Rate": float(
                        (aligned > 0).mean()
                    ),
                    "Median Return": float(
                        aligned.median()
                    ),
                    "Mean Return": float(
                        aligned.mean()
                    ),
                }
            )

    return pd.DataFrame(rows)


def _make_model() -> Pipeline:
    return Pipeline(
        [
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
            (
                "scale",
                StandardScaler(),
            ),
            (
                "model",
                LogisticRegression(
                    C=0.5,
                    max_iter=2000,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def _validation_label(
    metrics: Mapping[str, Any],
) -> str:
    n = int(
        metrics.get("oos_n", 0) or 0
    )
    folds = int(
        metrics.get("folds", 0) or 0
    )
    skill = _finite(
        metrics.get("brier_skill")
    )
    auc = _finite(
        metrics.get("roc_auc")
    )

    if n < 80 or folds < 3:
        return "INSUFFICIENT DATA"
    if np.isfinite(skill) and np.isfinite(auc):
        if (
            skill >= 0.03
            and auc >= 0.56
        ):
            return "PROMISING OOS"
        if (
            skill > 0.0
            and auc >= 0.53
        ):
            return "WEAK POSITIVE OOS"
    return "NO OOS EDGE"


def _walk_forward(
    events: pd.DataFrame,
    *,
    horizon: int,
    features: list[str],
) -> tuple[dict[str, Any], pd.DataFrame]:
    target_col = f"positive_{int(horizon)}w"
    data = events.dropna(
        subset=[
            target_col,
            "available_date",
        ]
    ).copy()

    if data.empty:
        return {
            "oos_n": 0,
            "folds": 0,
            "validation": (
                "INSUFFICIENT DATA"
            ),
        }, pd.DataFrame()

    for feature in features:
        if feature not in data.columns:
            data[feature] = np.nan

    data["available_date"] = pd.to_datetime(
        data["available_date"]
    )
    data["year"] = (
        data[
            "available_date"
        ].dt.year.astype(int)
    )

    oos_rows = []
    folds = 0

    for test_year in sorted(
        data["year"].unique().tolist()
    ):
        test_start = pd.Timestamp(
            year=int(test_year),
            month=1,
            day=1,
        )
        test_end = pd.Timestamp(
            year=int(test_year) + 1,
            month=1,
            day=1,
        )
        train_end = (
            test_start
            - pd.Timedelta(
                weeks=PURGE_WEEKS
            )
        )

        train = data[
            data["available_date"]
            < train_end
        ].copy()
        test = data[
            (
                data["available_date"]
                >= test_start
            )
            & (
                data["available_date"]
                < test_end
            )
        ].copy()

        if (
            len(train)
            < MIN_TRAIN_ROWS_FX
            or len(test)
            < MIN_TEST_ROWS_FX
            or train[
                target_col
            ].nunique()
            < 2
        ):
            continue

        model = _make_model()
        model.fit(
            train[features],
            train[
                target_col
            ].astype(int),
        )
        probability = model.predict_proba(
            test[features]
        )[:, 1]
        baseline_probability = float(
            train[
                target_col
            ].mean()
        )

        fold = test[
            [
                "pair",
                "available_date",
                "relation",
                target_col,
                f"return_{int(horizon)}w",
            ]
        ].copy()
        fold["probability"] = (
            probability
        )
        fold[
            "baseline_probability"
        ] = baseline_probability
        fold["test_year"] = int(
            test_year
        )
        oos_rows.append(fold)
        folds += 1

    if not oos_rows:
        metrics = {
            "oos_n": 0,
            "folds": 0,
            "positive_rate": (
                float(
                    data[
                        target_col
                    ].mean()
                )
                if len(data)
                else np.nan
            ),
            "brier_model": np.nan,
            "brier_baseline": np.nan,
            "brier_skill": np.nan,
            "roc_auc": np.nan,
            "validation": (
                "INSUFFICIENT DATA"
            ),
        }
        return metrics, pd.DataFrame()

    oos = pd.concat(
        oos_rows,
        ignore_index=True,
    )
    y = oos[
        target_col
    ].astype(int).to_numpy()
    p = oos[
        "probability"
    ].astype(float).to_numpy()
    p0 = oos[
        "baseline_probability"
    ].astype(float).to_numpy()

    brier_model = float(
        brier_score_loss(
            y,
            p,
        )
    )
    brier_baseline = float(
        brier_score_loss(
            y,
            p0,
        )
    )
    skill = (
        1.0
        - brier_model
        / brier_baseline
        if brier_baseline > 0
        else np.nan
    )
    auc = (
        float(
            roc_auc_score(
                y,
                p,
            )
        )
        if len(np.unique(y)) > 1
        else np.nan
    )

    metrics = {
        "oos_n": int(len(oos)),
        "folds": int(folds),
        "positive_rate": float(
            np.mean(y)
        ),
        "brier_model": brier_model,
        "brier_baseline": (
            brier_baseline
        ),
        "brier_skill": skill,
        "roc_auc": auc,
    }
    metrics["validation"] = (
        _validation_label(metrics)
    )
    return metrics, oos


def _ablation(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[int, str], pd.DataFrame]]:
    specs = [
        (
            "COT only",
            COT_FEATURES_FX,
        ),
        (
            "Rates only",
            RATES_FEATURES_FX,
        ),
        (
            "COT + Rates",
            COMBINED_FEATURES_FX,
        ),
    ]

    rows = []
    oos_map: dict[
        tuple[int, str],
        pd.DataFrame,
    ] = {}

    for horizon in RETURN_HORIZONS:
        horizon_rows = []
        for name, features in specs:
            metrics, oos = _walk_forward(
                events,
                horizon=horizon,
                features=features,
            )
            record = {
                "Horizont": f"{horizon}W",
                "Modell": name,
                **metrics,
            }
            rows.append(record)
            horizon_rows.append(record)
            oos_map[
                (horizon, name)
            ] = oos

        cot = next(
            (
                row
                for row in horizon_rows
                if row["Modell"]
                == "COT only"
            ),
            None,
        )
        if cot is not None:
            cot_brier = _finite(
                cot.get(
                    "brier_model"
                )
            )
            cot_auc = _finite(
                cot.get("roc_auc")
            )

            for row in rows:
                if (
                    row["Horizont"]
                    == f"{horizon}W"
                ):
                    model_brier = _finite(
                        row.get(
                            "brier_model"
                        )
                    )
                    model_auc = _finite(
                        row.get(
                            "roc_auc"
                        )
                    )
                    row[
                        "Δ Brier vs COT"
                    ] = (
                        cot_brier
                        - model_brier
                        if np.isfinite(
                            cot_brier
                        )
                        and np.isfinite(
                            model_brier
                        )
                        else np.nan
                    )
                    row[
                        "Δ AUC vs COT"
                    ] = (
                        model_auc
                        - cot_auc
                        if np.isfinite(
                            cot_auc
                        )
                        and np.isfinite(
                            model_auc
                        )
                        else np.nan
                    )

    return pd.DataFrame(rows), oos_map


def _incremental_read(
    ablation: pd.DataFrame,
    *,
    horizon: int = 4,
) -> dict[str, Any]:
    if ablation is None or ablation.empty:
        return {
            "label": (
                "INSUFFICIENT DATA"
            ),
        }

    subset = ablation[
        ablation["Horizont"].eq(
            f"{int(horizon)}W"
        )
    ]
    cot = subset[
        subset["Modell"].eq(
            "COT only"
        )
    ]
    combined = subset[
        subset["Modell"].eq(
            "COT + Rates"
        )
    ]
    rates = subset[
        subset["Modell"].eq(
            "Rates only"
        )
    ]

    if cot.empty or combined.empty:
        return {
            "label": (
                "INSUFFICIENT DATA"
            ),
        }

    cot_brier = _finite(
        cot.iloc[0].get(
            "brier_model"
        )
    )
    combined_brier = _finite(
        combined.iloc[0].get(
            "brier_model"
        )
    )
    cot_auc = _finite(
        cot.iloc[0].get(
            "roc_auc"
        )
    )
    combined_auc = _finite(
        combined.iloc[0].get(
            "roc_auc"
        )
    )
    rates_auc = (
        _finite(
            rates.iloc[0].get(
                "roc_auc"
            )
        )
        if not rates.empty
        else np.nan
    )

    brier_gain = (
        cot_brier
        - combined_brier
        if np.isfinite(cot_brier)
        and np.isfinite(
            combined_brier
        )
        else np.nan
    )
    auc_gain = (
        combined_auc
        - cot_auc
        if np.isfinite(cot_auc)
        and np.isfinite(
            combined_auc
        )
        else np.nan
    )

    if (
        np.isfinite(brier_gain)
        and np.isfinite(auc_gain)
        and brier_gain > 0.005
        and auc_gain >= 0.02
    ):
        label = (
            "RATES ADD INCREMENTAL "
            "FX INFORMATION"
        )
    elif (
        np.isfinite(brier_gain)
        and brier_gain > 0
        and np.isfinite(auc_gain)
        and auc_gain > 0
    ):
        label = (
            "SMALL INCREMENTAL "
            "RATES VALUE"
        )
    else:
        label = (
            "NO CLEAR INCREMENTAL "
            "RATES VALUE"
        )

    return {
        "label": label,
        "horizon": f"{int(horizon)}W",
        "brier_gain_vs_cot": (
            brier_gain
        ),
        "auc_gain_vs_cot": (
            auc_gain
        ),
        "rates_only_auc": rates_auc,
        "text": (
            "Primärvergleich: COT-only vs. "
            "COT+Rates auf denselben "
            "State-Change-Episoden."
        ),
    }


def _oos_by_pair(
    oos: pd.DataFrame,
    *,
    horizon: int,
) -> pd.DataFrame:
    if oos is None or oos.empty:
        return pd.DataFrame()

    target = (
        f"positive_{int(horizon)}w"
    )
    rows = []

    for pair, subset in oos.groupby(
        "pair"
    ):
        y = subset[
            target
        ].astype(int).to_numpy()
        p = subset[
            "probability"
        ].astype(float).to_numpy()
        p0 = subset[
            "baseline_probability"
        ].astype(float).to_numpy()

        if len(y) == 0:
            continue

        brier_model = float(
            brier_score_loss(
                y,
                p,
            )
        )
        brier_base = float(
            brier_score_loss(
                y,
                p0,
            )
        )
        skill = (
            1.0
            - brier_model
            / brier_base
            if brier_base > 0
            else np.nan
        )
        auc = (
            float(
                roc_auc_score(
                    y,
                    p,
                )
            )
            if len(np.unique(y)) > 1
            else np.nan
        )

        rows.append(
            {
                "Paar": pair,
                "n": int(len(y)),
                "Basisrate": float(
                    np.mean(y)
                ),
                "Brier Skill": skill,
                "ROC-AUC": auc,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            ["n", "Paar"],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )


def _fit_full_model(
    events: pd.DataFrame,
    *,
    horizon: int,
    features: list[str],
) -> Pipeline | None:
    target = (
        f"positive_{int(horizon)}w"
    )
    data = events.dropna(
        subset=[target]
    ).copy()

    if (
        len(data)
        < MIN_TRAIN_ROWS_FX
        or data[
            target
        ].nunique()
        < 2
    ):
        return None

    for feature in features:
        if feature not in data.columns:
            data[feature] = np.nan

    model = _make_model()
    model.fit(
        data[features],
        data[target].astype(int),
    )
    return model


def _current_probabilities(
    events: pd.DataFrame,
    weekly: pd.DataFrame,
    ablation: pd.DataFrame,
) -> pd.DataFrame:
    if (
        events is None
        or events.empty
        or weekly is None
        or weekly.empty
    ):
        return pd.DataFrame()

    current = (
        weekly.sort_values(
            "available_date"
        )
        .groupby(
            "pair",
            as_index=False,
        )
        .tail(1)
        .reset_index(drop=True)
    )

    models = {
        "P 4W · COT": _fit_full_model(
            events,
            horizon=4,
            features=COT_FEATURES_FX,
        ),
        "P 4W · Rates": _fit_full_model(
            events,
            horizon=4,
            features=RATES_FEATURES_FX,
        ),
        "P 4W · Combined": _fit_full_model(
            events,
            horizon=4,
            features=COMBINED_FEATURES_FX,
        ),
    }

    result = current[
        [
            "pair",
            "relation",
            "available_date",
            "cot_pair_direction",
            "rates20_direction",
            "rates20_percentile",
            "rates_alignment_count",
        ]
    ].copy()

    for label, model in models.items():
        if model is None:
            result[label] = np.nan
            continue

        features = (
            COT_FEATURES_FX
            if label == "P 4W · COT"
            else RATES_FEATURES_FX
            if label == "P 4W · Rates"
            else COMBINED_FEATURES_FX
        )
        frame = current.copy()
        for feature in features:
            if feature not in frame.columns:
                frame[feature] = np.nan

        result[label] = model.predict_proba(
            frame[features]
        )[:, 1]

    four_week = (
        ablation[
            ablation[
                "Horizont"
            ].eq("4W")
        ]
        if (
            ablation is not None
            and not ablation.empty
        )
        else pd.DataFrame()
    )
    combined = (
        four_week[
            four_week[
                "Modell"
            ].eq(
                "COT + Rates"
            )
        ]
        if not four_week.empty
        else pd.DataFrame()
    )
    validation = (
        str(
            combined.iloc[0].get(
                "validation",
                "INSUFFICIENT DATA",
            )
        )
        if not combined.empty
        else "INSUFFICIENT DATA"
    )
    result[
        "Combined OOS"
    ] = validation

    return result.sort_values(
        "P 4W · Combined",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)


def run_yield_cot_fx_return_study() -> dict[str, Any]:
    """Run COT x 2Y Rates directly against subsequent FX returns."""
    yield_universe = (
        fetch_yield_universe()
    )
    rate_currencies = {
        currency
        for currency, result in yield_universe.items()
        if (
            currency in PAIR_CURRENCY_ORDER
            and not _clean_rate_series(
                result
            ).empty
        )
    }

    cot_histories, cot_errors = (
        _load_cot_state_histories(
            set(rate_currencies)
        )
    )
    common = set(
        cot_histories
    ).intersection(
        rate_currencies
    )

    fx_values = (
        load_currency_usd_values(
            start="2000-01-01"
        )
    )
    common = common.intersection(
        set(fx_values)
    )

    common_cot = {
        currency: cot_histories[currency]
        for currency in common
    }
    common_yields = {
        currency: yield_universe[currency]
        for currency in common
    }
    common_fx = {
        currency: fx_values[currency]
        for currency in common
    }

    weekly, state_errors = (
        _build_pair_weekly_states(
            common_cot,
            common_yields,
            common_fx,
        )
    )

    events = (
        weekly[
            weekly[
                "episode_start"
            ].fillna(False)
            & ~weekly[
                "relation"
            ].eq("NEUTRAL")
        ]
        .copy()
        .reset_index(drop=True)
        if not weekly.empty
        else pd.DataFrame()
    )

    events = _attach_fx_returns(
        events,
        common_fx,
    )

    baseline = _baseline_table(
        events
    )
    ablation, oos_map = _ablation(
        events
    )
    incremental = _incremental_read(
        ablation,
        horizon=4,
    )
    combined_oos_4w = oos_map.get(
        (4, "COT + Rates"),
        pd.DataFrame(),
    )
    by_pair = _oos_by_pair(
        combined_oos_4w,
        horizon=4,
    )
    current = _current_probabilities(
        events,
        weekly,
        ablation,
    )

    all_errors = list(cot_errors)
    all_errors.extend(state_errors)

    known_8w = (
        int(
            events[
                "return_8w"
            ].notna().sum()
        )
        if (
            not events.empty
            and "return_8w"
            in events.columns
        )
        else 0
    )

    meta = {
        "currencies": sorted(common),
        "pairs": (
            int(
                weekly[
                    "pair"
                ].nunique()
            )
            if not weekly.empty
            else 0
        ),
        "weekly_states": int(
            len(weekly)
        ),
        "episodes": int(
            len(events)
        ),
        "known_8w_returns": known_8w,
        "first_event": (
            _naive_ts(
                events[
                    "available_date"
                ].min()
            )
            if not events.empty
            else pd.NaT
        ),
        "last_event": (
            _naive_ts(
                events[
                    "available_date"
                ].max()
            )
            if not events.empty
            else pd.NaT
        ),
        "rates_safety_lag_bdays": (
            RATES_INFORMATION_LAG_BDAYS
        ),
        "purge_weeks": PURGE_WEEKS,
    }

    return {
        "meta": meta,
        "baseline": baseline,
        "ablation": ablation,
        "incremental_read": incremental,
        "current": current,
        "oos_by_pair": by_pair,
        "errors": pd.DataFrame(
            all_errors
        ),
        "events": events,
        "weekly": weekly,
    }


__all__ = [
    "run_yield_cot_fx_return_study",
    "classify_pair_state",
    "_forward_return_after",
    "_baseline_table",
    "COT_FEATURES_FX",
    "RATES_FEATURES_FX",
    "COMBINED_FEATURES_FX",
]
