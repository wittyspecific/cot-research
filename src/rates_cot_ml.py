from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .analysis import enrich_cot, hedger_cycle_state
from .cftc import load_cftc_universe, load_history, resolve_market
from .config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
)
from .markets import CLASSIC_MARKETS
from .publication import backtest_available_date
from .yield_spreads import fetch_yield_universe, spread_series


# V3.18.0 · RATES ↔ COT LEAD/LAG ML RESEARCH
#
# Research question:
#   When historically significant 20D 2Y-rate repricing appears before the
#   COT macro state, how often does COT move into the same direction later?
#
# Research safety:
#   * event-driven samples (first observation of each independent lead episode)
#   * no random train/test mixing
#   * yearly walk-forward validation
#   * 8-week purge before each test year
#   * conservative COT information-availability anchor
#   * additional rates information lag
#   * no trade/watchlist/risk/execution mutation

HORIZONS = (5, 20, 60)
TARGET_HORIZONS = (2, 4, 6, 8)
MEANINGFUL_PERCENTILE = 75.0
MIN_MEANINGFUL_COMPARISONS = 2
NORMALIZATION_LOOKBACK_YEARS = 5
NORMALIZATION_MIN_HISTORY = 252
RATES_INFORMATION_LAG_BDAYS = 5
PURGE_WEEKS = 8
MIN_TRAIN_ROWS = 50
MIN_TEST_ROWS = 4

PHASE_CODE = {
    "NEUTRAL": 0,
    "EXTREME": 1,
    "TRANSITION": 2,
    "RELEASE": 3,
}

FEATURES = [
    "rates20_percentile",
    "rates20_magnitude_bp",
    "rates20_meaningful",
    "rates20_vote_margin",
    "rates5_confirms",
    "rates5_opposes",
    "rates5_percentile",
    "rates60_confirms",
    "rates60_opposes",
    "rates60_percentile",
    "cot_phase_code",
    "cot_opposite",
    "cot_neutral",
    "cot_extreme_same",
    "commercial_percentile",
    "cot_delta_1w",
    "cot_delta_2w",
    "cot_delta_4w",
    "distance_from_extreme",
]


def _finite(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _naive_ts(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts


def _clean_rate_series(result: Any) -> pd.Series:
    series = getattr(result, "series", None)
    if series is None:
        return pd.Series(dtype=float)
    out = pd.Series(series).copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = pd.to_numeric(out, errors="coerce")
    out = out[~out.index.isna()].dropna().sort_index()
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)
    return out[~out.index.duplicated(keep="last")].astype(float)


def _macro_from_cycle(cycle: Mapping[str, Any]) -> tuple[str, int, bool]:
    raw_phase = str(cycle.get("phase", "") or "").upper()
    transition = str(cycle.get("transition", "") or "").upper()
    release_direction = int(np.sign(_finite(cycle.get("direction"), 0.0)))
    extreme_direction = int(
        np.sign(_finite(cycle.get("extreme_direction"), 0.0))
    )

    if raw_phase == "RELEASE" and release_direction != 0:
        return "RELEASE", release_direction, True
    if (
        raw_phase == "TRANSITION"
        or "EARLY RELEASE" in transition
    ) and extreme_direction != 0:
        return "TRANSITION", extreme_direction, False
    if raw_phase == "EXTREME" and extreme_direction != 0:
        return "EXTREME", extreme_direction, False
    return "NEUTRAL", 0, False


def _load_cot_state_histories(
    currencies: set[str],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, str]]]:
    universe = load_cftc_universe()
    histories: dict[str, pd.DataFrame] = {}
    errors: list[dict[str, str]] = []

    markets = {
        str(market.get("symbol", "") or "").upper(): market
        for market in CLASSIC_MARKETS.get("Currencies", [])
    }

    for currency in sorted(currencies):
        market = markets.get(currency)
        if market is None:
            errors.append(
                {
                    "currency": currency,
                    "stage": "COT",
                    "error": "Kein Currency-Market-Mapping vorhanden.",
                }
            )
            continue

        try:
            resolved = resolve_market(market, universe)
            if not resolved:
                raise RuntimeError("CFTC-Serie konnte nicht aufgelöst werden.")
            code = str(resolved["cftc_contract_market_code"])
            raw = load_history(code)
            if raw is None or raw.empty:
                raise RuntimeError("Keine COT-Historie.")

            cot = enrich_cot(
                raw,
                weeks=COT_INDEX_WEEKS,
                validation_weeks=NET_VALIDATION_WEEKS,
                range_weeks=COMMERCIAL_RANGE_WEEKS,
            ).reset_index(drop=True)

            rows = []
            for i in range(len(cot)):
                current = cot.iloc[i]
                if pd.isna(current.get("commercial_net_percentile")):
                    continue

                cycle = hedger_cycle_state(
                    cot.iloc[: i + 1],
                    upper=NET_UPPER_PERCENTILE,
                    lower=NET_LOWER_PERCENTILE,
                )
                phase, direction, active = _macro_from_cycle(cycle)
                report_date = _naive_ts(current["report_date"])
                available_date = _naive_ts(
                    backtest_available_date(report_date)
                )

                rows.append(
                    {
                        "currency": currency,
                        "report_date": report_date,
                        "available_date": available_date,
                        "cot_phase": phase,
                        "cot_direction": int(direction),
                        "cot_active": bool(active),
                        "commercial_percentile": _finite(
                            current.get("commercial_net_percentile")
                        ),
                        "cot_delta_1w": _finite(
                            cycle.get("percentile_change_1w")
                        ),
                        "cot_delta_2w": _finite(
                            cycle.get("percentile_change_2w")
                        ),
                        "cot_delta_4w": _finite(
                            cycle.get("percentile_change_4w")
                        ),
                        "distance_from_extreme": _finite(
                            cycle.get("distance_from_extreme")
                        ),
                    }
                )

            frame = pd.DataFrame(rows)
            if frame.empty:
                raise RuntimeError(
                    "Keine historisch rekonstruierbaren 156W-Zustände."
                )
            histories[currency] = (
                frame.sort_values("available_date")
                .drop_duplicates("available_date", keep="last")
                .reset_index(drop=True)
            )
        except Exception as exc:
            errors.append(
                {
                    "currency": currency,
                    "stage": "COT",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return histories, errors


def _move_arrays(
    spread: pd.Series,
    periods: int,
) -> tuple[np.ndarray, np.ndarray]:
    clean = spread.dropna().sort_index()
    if len(clean) <= int(periods):
        return (
            np.asarray([], dtype="datetime64[ns]"),
            np.asarray([], dtype=float),
        )
    moves = (clean.diff(int(periods)) * 100.0).dropna()
    if moves.empty:
        return (
            np.asarray([], dtype="datetime64[ns]"),
            np.asarray([], dtype=float),
        )
    return (
        moves.index.to_numpy(dtype="datetime64[ns]"),
        moves.to_numpy(dtype=float),
    )


def _historical_move_stats_lookup(
    move_dates: np.ndarray,
    move_values: np.ndarray,
    asof_date,
) -> dict[str, Any]:
    if len(move_dates) == 0:
        return {"delta_bp": np.nan, "percentile": np.nan, "history_count": 0}

    cutoff_np = np.datetime64(_naive_ts(asof_date).to_datetime64())
    pos = int(np.searchsorted(move_dates, cutoff_np, side="right") - 1)
    if pos < 0:
        return {"delta_bp": np.nan, "percentile": np.nan, "history_count": 0}

    current_move = float(move_values[pos])
    current_date = _naive_ts(move_dates[pos])
    history_values = move_values[:pos]
    history_dates = move_dates[:pos]

    cutoff = current_date - pd.DateOffset(
        years=NORMALIZATION_LOOKBACK_YEARS
    )
    cutoff_hist_np = np.datetime64(cutoff.to_datetime64())
    recent_start = int(
        np.searchsorted(history_dates, cutoff_hist_np, side="left")
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
    percentile = max(0.0, min(100.0, float(percentile)))

    return {
        "delta_bp": current_move,
        "percentile": percentile,
        "history_count": int(len(hist_abs)),
    }


def _historical_move_stats_asof(
    spread: pd.Series,
    asof_date,
    periods: int,
) -> dict[str, Any]:
    move_dates, move_values = _move_arrays(spread, periods)
    return _historical_move_stats_lookup(
        move_dates,
        move_values,
        asof_date,
    )


def _canonical_spread(
    a: str,
    b: str,
    universe: Mapping[str, Any],
    spread_cache: dict[tuple[str, str], pd.Series],
) -> tuple[pd.Series, int]:
    left, right = sorted((str(a), str(b)))
    key = (left, right)
    if key not in spread_cache:
        spread_cache[key] = spread_series(
            _clean_rate_series(universe.get(left)),
            _clean_rate_series(universe.get(right)),
            name=f"{left}{right}",
        )
    sign = 1 if str(a) == left else -1
    return spread_cache[key], sign


def _pair_stats(
    base: str,
    peer: str,
    asof_date,
    horizon: int,
    universe: Mapping[str, Any],
    spread_cache: dict[tuple[str, str], pd.Series],
    move_cache: dict[tuple[str, str, int], tuple[np.ndarray, np.ndarray]],
    stats_cache: dict[tuple[str, str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    cutoff = _naive_ts(asof_date) - pd.offsets.BDay(
        RATES_INFORMATION_LAG_BDAYS
    )
    left, right = sorted((str(base), str(peer)))
    cache_key = (
        left,
        right,
        cutoff.strftime("%Y-%m-%d"),
        int(horizon),
    )

    if cache_key not in stats_cache:
        spread, _ = _canonical_spread(
            left, right, universe, spread_cache
        )
        move_key = (left, right, int(horizon))
        if move_key not in move_cache:
            move_cache[move_key] = _move_arrays(spread, horizon)
        move_dates, move_values = move_cache[move_key]
        stats_cache[cache_key] = _historical_move_stats_lookup(
            move_dates,
            move_values,
            cutoff,
        )

    canonical = stats_cache[cache_key]
    sign = 1 if str(base) == left else -1
    delta = _finite(canonical.get("delta_bp"))
    if np.isfinite(delta):
        delta *= sign

    return {
        "delta_bp": delta,
        "percentile": _finite(canonical.get("percentile")),
        "history_count": int(canonical.get("history_count", 0) or 0),
    }


def _rates_consensus_at(
    currency: str,
    asof_date,
    universe: Mapping[str, Any],
    *,
    horizon: int,
    usable_currencies: tuple[str, ...],
    spread_cache: dict[tuple[str, str], pd.Series],
    move_cache: dict[tuple[str, str, int], tuple[np.ndarray, np.ndarray]],
    stats_cache: dict[tuple[str, str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    observations = []
    for peer in usable_currencies:
        if peer == currency:
            continue

        stats = _pair_stats(
            currency,
            peer,
            asof_date,
            horizon,
            universe,
            spread_cache,
            move_cache,
            stats_cache,
        )
        delta = _finite(stats.get("delta_bp"))
        percentile = _finite(stats.get("percentile"))
        if not np.isfinite(delta) or not np.isfinite(percentile):
            continue

        observations.append(
            {
                "peer": peer,
                "delta_bp": float(delta),
                "percentile": float(percentile),
                "direction": 1 if delta > 0 else -1 if delta < 0 else 0,
                "meaningful": bool(
                    percentile >= MEANINGFUL_PERCENTILE
                    and delta != 0
                ),
            }
        )

    meaningful = [x for x in observations if x["meaningful"]]
    bullish = [x for x in meaningful if x["direction"] > 0]
    bearish = [x for x in meaningful if x["direction"] < 0]

    direction = 0
    winners = []
    if len(meaningful) >= MIN_MEANINGFUL_COMPARISONS:
        if len(bullish) > len(bearish):
            direction = 1
            winners = bullish
        elif len(bearish) > len(bullish):
            direction = -1
            winners = bearish

    return {
        "direction": int(direction),
        "available": int(len(observations)),
        "meaningful": int(len(meaningful)),
        "vote_margin": int(abs(len(bullish) - len(bearish))),
        "median_percentile": (
            float(np.median([x["percentile"] for x in winners]))
            if winners
            else np.nan
        ),
        "median_delta_bp": (
            float(np.median([x["delta_bp"] for x in winners]))
            if winners
            else np.nan
        ),
    }


def _relation_label(
    cot_phase: str,
    cot_direction: int,
    rates_direction: int,
) -> str:
    if rates_direction == 0:
        return "NO_RATES"
    if cot_direction == -rates_direction and cot_direction != 0:
        return "CONFLICT"
    if cot_direction == 0:
        return "COT_NEUTRAL"
    if cot_direction == rates_direction:
        if cot_phase == "EXTREME":
            return "SAME_EXTREME"
        if cot_phase == "TRANSITION":
            return "SAME_TRANSITION"
        if cot_phase == "RELEASE":
            return "ALREADY_RELEASED"
    return "OTHER"


def _build_candidate_rows(
    cot_histories: Mapping[str, pd.DataFrame],
    universe: Mapping[str, Any],
) -> pd.DataFrame:
    usable = tuple(
        sorted(
            currency
            for currency in cot_histories
            if currency in universe
            and not _clean_rate_series(universe[currency]).empty
        )
    )
    if len(usable) < 3:
        return pd.DataFrame()

    spread_cache: dict[tuple[str, str], pd.Series] = {}
    move_cache: dict[tuple[str, str, int], tuple[np.ndarray, np.ndarray]] = {}
    stats_cache: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    rows = []

    for currency in usable:
        history = cot_histories[currency]
        for _, cot_row in history.iterrows():
            available_date = _naive_ts(cot_row["available_date"])
            rates = {
                horizon: _rates_consensus_at(
                    currency,
                    available_date,
                    universe,
                    horizon=horizon,
                    usable_currencies=usable,
                    spread_cache=spread_cache,
                    move_cache=move_cache,
                    stats_cache=stats_cache,
                )
                for horizon in HORIZONS
            }

            r20 = rates[20]
            rates_direction = int(r20["direction"])
            if rates_direction == 0:
                continue

            cot_phase = str(cot_row["cot_phase"])
            cot_direction = int(cot_row["cot_direction"])
            relation = _relation_label(
                cot_phase,
                cot_direction,
                rates_direction,
            )

            # If COT is already transitioning/released in the same direction,
            # this is confirmation, not a Rates->COT lead candidate.
            if relation in {"SAME_TRANSITION", "ALREADY_RELEASED", "OTHER"}:
                continue

            r5 = rates[5]
            r60 = rates[60]
            rows.append(
                {
                    **cot_row.to_dict(),
                    "rates_direction": rates_direction,
                    "relation": relation,
                    "rates20_percentile": _finite(
                        r20["median_percentile"]
                    ),
                    "rates20_magnitude_bp": abs(
                        _finite(r20["median_delta_bp"])
                    ),
                    "rates20_meaningful": int(r20["meaningful"]),
                    "rates20_vote_margin": int(r20["vote_margin"]),
                    "rates5_direction": int(r5["direction"]),
                    "rates5_percentile": _finite(
                        r5["median_percentile"]
                    ),
                    "rates5_confirms": int(
                        int(r5["direction"]) == rates_direction
                    ),
                    "rates5_opposes": int(
                        int(r5["direction"]) == -rates_direction
                        and int(r5["direction"]) != 0
                    ),
                    "rates60_direction": int(r60["direction"]),
                    "rates60_percentile": _finite(
                        r60["median_percentile"]
                    ),
                    "rates60_confirms": int(
                        int(r60["direction"]) == rates_direction
                    ),
                    "rates60_opposes": int(
                        int(r60["direction"]) == -rates_direction
                        and int(r60["direction"]) != 0
                    ),
                    "cot_phase_code": int(
                        PHASE_CODE.get(cot_phase, 0)
                    ),
                    "cot_opposite": int(
                        cot_direction == -rates_direction
                        and cot_direction != 0
                    ),
                    "cot_neutral": int(cot_direction == 0),
                    "cot_extreme_same": int(
                        cot_direction == rates_direction
                        and cot_phase == "EXTREME"
                    ),
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.sort_values(
        ["currency", "available_date"]
    ).reset_index(drop=True)

    episode_id = 0
    episode_ids = []
    episode_ages = []
    episode_starts = []

    for _, group in frame.groupby("currency", sort=False):
        previous_date = None
        previous_direction = None
        age = 0

        for idx in group.index:
            row = frame.loc[idx]
            current_date = _naive_ts(row["available_date"])
            current_direction = int(row["rates_direction"])
            is_start = (
                previous_date is None
                or (current_date - previous_date).days > 10
                or current_direction != previous_direction
            )
            if is_start:
                episode_id += 1
                age = 0
            else:
                age += 1

            episode_ids.append((idx, episode_id))
            episode_ages.append((idx, age))
            episode_starts.append((idx, is_start))

            previous_date = current_date
            previous_direction = current_direction

    for idx, value in episode_ids:
        frame.loc[idx, "episode_id"] = int(value)
    for idx, value in episode_ages:
        frame.loc[idx, "episode_age_weeks"] = int(value)
    for idx, value in episode_starts:
        frame.loc[idx, "episode_start"] = bool(value)

    frame["episode_id"] = frame["episode_id"].astype(int)
    frame["episode_age_weeks"] = frame["episode_age_weeks"].astype(int)
    frame["episode_start"] = frame["episode_start"].astype(bool)
    return frame


def _future_target(
    history: pd.DataFrame,
    current_date,
    direction: int,
    horizon_weeks: int,
    *,
    target: str,
) -> tuple[float, float]:
    current = _naive_ts(current_date)
    end = current + pd.Timedelta(weeks=int(horizon_weeks))
    max_known = _naive_ts(history["available_date"].max())

    future = history[
        (history["available_date"] > current)
        & (history["available_date"] <= min(end, max_known))
    ].copy()

    if target == "transition":
        mask = (
            future["cot_direction"].eq(int(direction))
            & future["cot_phase"].isin(["TRANSITION", "RELEASE"])
        )
    elif target == "release":
        mask = (
            future["cot_direction"].eq(int(direction))
            & future["cot_phase"].eq("RELEASE")
        )
    else:
        raise ValueError(target)

    matched = future[mask]
    if not matched.empty:
        first = _naive_ts(matched.iloc[0]["available_date"])
        return 1.0, float((first - current).days)

    if max_known < end:
        return np.nan, np.nan
    return 0.0, np.nan


def _attach_targets(
    events: pd.DataFrame,
    cot_histories: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame() if events is None else events.copy()

    out = events.copy()
    for horizon in TARGET_HORIZONS:
        out[f"transition_{horizon}w"] = np.nan
        out[f"release_{horizon}w"] = np.nan
    out["transition_lead_days_8w"] = np.nan
    out["release_lead_days_8w"] = np.nan

    for idx, row in out.iterrows():
        history = cot_histories.get(str(row["currency"]))
        if history is None or history.empty:
            continue

        direction = int(row["rates_direction"])
        current_date = row["available_date"]
        for horizon in TARGET_HORIZONS:
            transition, transition_days = _future_target(
                history,
                current_date,
                direction,
                horizon,
                target="transition",
            )
            release, release_days = _future_target(
                history,
                current_date,
                direction,
                horizon,
                target="release",
            )
            out.loc[idx, f"transition_{horizon}w"] = transition
            out.loc[idx, f"release_{horizon}w"] = release
            if horizon == 8:
                out.loc[idx, "transition_lead_days_8w"] = transition_days
                out.loc[idx, "release_lead_days_8w"] = release_days

    return out


def _episode_baseline(events: pd.DataFrame) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()

    rows = []
    for relation in ("ALL", "CONFLICT", "COT_NEUTRAL", "SAME_EXTREME"):
        subset = events if relation == "ALL" else events[events["relation"].eq(relation)]
        if subset.empty:
            continue

        record: dict[str, Any] = {
            "Gruppe": relation,
            "Episoden": int(len(subset)),
        }
        for horizon in TARGET_HORIZONS:
            known = subset[f"release_{horizon}w"].dropna()
            record[f"Release ≤{horizon}W"] = (
                float(known.mean()) if len(known) else np.nan
            )
        transition = subset["transition_6w"].dropna()
        record["Transition ≤6W"] = (
            float(transition.mean()) if len(transition) else np.nan
        )
        lead = subset["release_lead_days_8w"].dropna()
        record["Median Lead Tage"] = (
            float(lead.median()) if len(lead) else np.nan
        )
        rows.append(record)

    return pd.DataFrame(rows)


def _make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
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


def _validation_label(metrics: Mapping[str, Any]) -> str:
    n = int(metrics.get("oos_n", 0) or 0)
    folds = int(metrics.get("folds", 0) or 0)
    skill = _finite(metrics.get("brier_skill"))
    auc = _finite(metrics.get("roc_auc"))

    if n < 30 or folds < 2:
        return "INSUFFICIENT DATA"
    if np.isfinite(skill) and np.isfinite(auc):
        if skill >= 0.05 and auc >= 0.58:
            return "PROMISING OOS"
        if skill > 0.0 and auc >= 0.53:
            return "WEAK POSITIVE OOS"
    return "NO OOS EDGE"


def _walk_forward_model(
    events: pd.DataFrame,
    *,
    target_col: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    data = events.dropna(subset=[target_col, "available_date"]).copy()
    if data.empty:
        return {
            "target": target_col,
            "oos_n": 0,
            "folds": 0,
            "validation": "INSUFFICIENT DATA",
        }, pd.DataFrame()

    data["available_date"] = pd.to_datetime(data["available_date"])
    data["year"] = data["available_date"].dt.year.astype(int)
    oos_rows = []
    folds = 0

    for test_year in sorted(data["year"].unique().tolist()):
        test_start = pd.Timestamp(year=int(test_year), month=1, day=1)
        test_end = pd.Timestamp(year=int(test_year) + 1, month=1, day=1)
        train_end = test_start - pd.Timedelta(weeks=PURGE_WEEKS)

        train = data[data["available_date"] < train_end]
        test = data[
            (data["available_date"] >= test_start)
            & (data["available_date"] < test_end)
        ]

        if (
            len(train) < MIN_TRAIN_ROWS
            or len(test) < MIN_TEST_ROWS
            or train[target_col].nunique() < 2
        ):
            continue

        model = _make_model()
        model.fit(train[FEATURES], train[target_col].astype(int))
        probability = model.predict_proba(test[FEATURES])[:, 1]
        baseline_probability = float(train[target_col].mean())

        fold = test[
            [
                "currency",
                "available_date",
                "relation",
                target_col,
            ]
        ].copy()
        fold["probability"] = probability
        fold["baseline_probability"] = baseline_probability
        fold["test_year"] = int(test_year)
        oos_rows.append(fold)
        folds += 1

    if not oos_rows:
        return {
            "target": target_col,
            "oos_n": 0,
            "folds": 0,
            "validation": "INSUFFICIENT DATA",
        }, pd.DataFrame()

    oos = pd.concat(oos_rows, ignore_index=True)
    y = oos[target_col].astype(int).to_numpy()
    p = oos["probability"].astype(float).to_numpy()
    p0 = oos["baseline_probability"].astype(float).to_numpy()

    brier_model = float(brier_score_loss(y, p))
    brier_baseline = float(brier_score_loss(y, p0))
    brier_skill = (
        1.0 - brier_model / brier_baseline
        if brier_baseline > 0
        else np.nan
    )
    auc = (
        float(roc_auc_score(y, p))
        if len(np.unique(y)) > 1
        else np.nan
    )

    metrics = {
        "target": target_col,
        "oos_n": int(len(oos)),
        "folds": int(folds),
        "positive_rate": float(np.mean(y)),
        "brier_model": brier_model,
        "brier_baseline": brier_baseline,
        "brier_skill": brier_skill,
        "roc_auc": auc,
    }
    metrics["validation"] = _validation_label(metrics)
    return metrics, oos


def _fit_full_model(
    events: pd.DataFrame,
    *,
    target_col: str,
) -> Pipeline | None:
    data = events.dropna(subset=[target_col]).copy()
    if len(data) < MIN_TRAIN_ROWS or data[target_col].nunique() < 2:
        return None
    model = _make_model()
    model.fit(data[FEATURES], data[target_col].astype(int))
    return model


def _coefficient_table(model: Pipeline | None) -> pd.DataFrame:
    if model is None:
        return pd.DataFrame()
    classifier = model.named_steps["model"]
    coefficients = classifier.coef_[0]
    out = pd.DataFrame(
        {
            "Feature": FEATURES,
            "Koeffizient": coefficients,
            "Abs": np.abs(coefficients),
        }
    )
    return (
        out.sort_values("Abs", ascending=False)
        .drop(columns="Abs")
        .reset_index(drop=True)
    )


def _calibration_table(
    oos: pd.DataFrame,
    target_col: str,
) -> pd.DataFrame:
    if oos is None or oos.empty:
        return pd.DataFrame()

    frame = oos.copy()
    frame["Bucket"] = pd.cut(
        frame["probability"],
        bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.000001],
        labels=["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"],
        include_lowest=True,
        right=False,
    )
    return (
        frame.dropna(subset=["Bucket"])
        .groupby("Bucket", observed=True)
        .agg(
            Fälle=(target_col, "size"),
            Modell=("probability", "mean"),
            Realisiert=(target_col, "mean"),
        )
        .reset_index()
    )


def _current_candidates(
    candidates: pd.DataFrame,
    cot_histories: Mapping[str, pd.DataFrame],
    transition_model: Pipeline | None,
    release_model: Pipeline | None,
    transition_metrics: Mapping[str, Any],
    release_metrics: Mapping[str, Any],
    events: pd.DataFrame,
) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()

    rows = []
    for currency, group in candidates.groupby("currency"):
        history = cot_histories.get(str(currency))
        if history is None or history.empty:
            continue

        latest_cot_date = _naive_ts(history["available_date"].max())
        latest = group.sort_values("available_date").iloc[-1]
        latest_candidate_date = _naive_ts(latest["available_date"])
        if (latest_cot_date - latest_candidate_date).days > 10:
            continue

        episode_id = int(latest["episode_id"])
        episode = group[group["episode_id"].eq(episode_id)].sort_values(
            "available_date"
        )
        start = episode.iloc[0]

        p_transition = np.nan
        p_release = np.nan
        if transition_model is not None:
            p_transition = float(
                transition_model.predict_proba(
                    pd.DataFrame([start[FEATURES].to_dict()])
                )[0, 1]
            )
        if release_model is not None:
            p_release = float(
                release_model.predict_proba(
                    pd.DataFrame([start[FEATURES].to_dict()])
                )[0, 1]
            )

        known_transition = events["transition_6w"].dropna()
        known_release = events["release_8w"].dropna()

        rows.append(
            {
                "currency": currency,
                "episode_start": _naive_ts(start["available_date"]),
                "episode_age_weeks": int(latest["episode_age_weeks"]),
                "relation": str(latest["relation"]),
                "cot_phase": str(latest["cot_phase"]),
                "cot_direction": int(latest["cot_direction"]),
                "rates_direction": int(latest["rates_direction"]),
                "start_20d_percentile": _finite(start["rates20_percentile"]),
                "current_20d_percentile": _finite(latest["rates20_percentile"]),
                "current_20d_magnitude_bp": _finite(
                    latest["rates20_magnitude_bp"]
                ),
                "current_5d_confirms": int(latest["rates5_confirms"]),
                "current_60d_confirms": int(latest["rates60_confirms"]),
                "P Transition ≤6W": p_transition,
                "P Release ≤8W": p_release,
                "Baseline Transition ≤6W": (
                    float(known_transition.mean())
                    if len(known_transition)
                    else np.nan
                ),
                "Baseline Release ≤8W": (
                    float(known_release.mean())
                    if len(known_release)
                    else np.nan
                ),
                "Transition OOS": str(
                    transition_metrics.get(
                        "validation", "INSUFFICIENT DATA"
                    )
                ),
                "Release OOS": str(
                    release_metrics.get(
                        "validation", "INSUFFICIENT DATA"
                    )
                ),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        "P Release ≤8W",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)


def run_rates_cot_ml_study() -> dict[str, Any]:
    """Run the complete event-driven, walk-forward Rates -> COT study."""
    yield_universe = fetch_yield_universe()
    rate_currencies = {
        str(currency)
        for currency, result in yield_universe.items()
        if not _clean_rate_series(result).empty
    }

    cot_histories, errors = _load_cot_state_histories(rate_currencies)
    common = set(cot_histories).intersection(rate_currencies)
    common_cot = {currency: cot_histories[currency] for currency in common}
    common_yields = {currency: yield_universe[currency] for currency in common}

    candidates = _build_candidate_rows(common_cot, common_yields)
    events = (
        candidates[candidates["episode_start"]].copy().reset_index(drop=True)
        if not candidates.empty
        else pd.DataFrame()
    )
    events = _attach_targets(events, common_cot)
    baseline = _episode_baseline(events)

    transition_metrics, transition_oos = _walk_forward_model(
        events,
        target_col="transition_6w",
    )
    release_metrics, release_oos = _walk_forward_model(
        events,
        target_col="release_8w",
    )

    transition_model = _fit_full_model(
        events,
        target_col="transition_6w",
    )
    release_model = _fit_full_model(
        events,
        target_col="release_8w",
    )

    current = _current_candidates(
        candidates,
        common_cot,
        transition_model,
        release_model,
        transition_metrics,
        release_metrics,
        events,
    )

    metrics = pd.DataFrame(
        [
            {"Modell": "Transition ≤6W", **transition_metrics},
            {"Modell": "Release ≤8W", **release_metrics},
        ]
    )

    meta = {
        "currencies": sorted(common),
        "candidate_weeks": int(len(candidates)),
        "episodes": int(len(events)),
        "known_transition": int(events["transition_6w"].notna().sum())
        if not events.empty
        else 0,
        "known_release": int(events["release_8w"].notna().sum())
        if not events.empty
        else 0,
        "first_event": _naive_ts(events["available_date"].min())
        if not events.empty
        else pd.NaT,
        "last_event": _naive_ts(events["available_date"].max())
        if not events.empty
        else pd.NaT,
        "rates_information_lag_bdays": RATES_INFORMATION_LAG_BDAYS,
        "purge_weeks": PURGE_WEEKS,
    }

    return {
        "meta": meta,
        "baseline": baseline,
        "metrics": metrics,
        "current": current,
        "transition_coefficients": _coefficient_table(transition_model),
        "release_coefficients": _coefficient_table(release_model),
        "transition_calibration": _calibration_table(
            transition_oos, "transition_6w"
        ),
        "release_calibration": _calibration_table(
            release_oos, "release_8w"
        ),
        "errors": pd.DataFrame(errors),
        "events": events,
    }


__all__ = [
    "run_rates_cot_ml_study",
    "_historical_move_stats_asof",
    "_attach_targets",
    "_episode_baseline",
    "_walk_forward_model",
    "FEATURES",
]

# V3.18.1 · RATES COT ML DEEP DIVE
#
# Purpose:
#   1) Feature ablation on the exact same Rates-lead event sample
#   2) Strict lead test: CONFLICT + COT_NEUTRAL only
#   3) Sequence baselines: do 5D / 60D confirmations matter?
#   4) Robustness by year, currency and time-aware leave-one-currency-out
#
# Important methodological wording:
# "COT-State only" is conditional on a qualifying Rates episode existing.
# The event sample itself is Rates-defined; the ablation asks whether Rates
# intensity/confirmation adds information beyond the current COT state.

RELATION_ONLY_FEATURES_V3181 = [
    "cot_opposite",
    "cot_neutral",
    "cot_extreme_same",
]

COT_STATE_FEATURES_V3181 = [
    "cot_phase_code",
    "cot_opposite",
    "cot_neutral",
    "cot_extreme_same",
    "commercial_percentile",
    "cot_delta_1w",
    "cot_delta_2w",
    "cot_delta_4w",
    "distance_from_extreme",
]

RATES_ONLY_FEATURES_V3181 = [
    "rates20_percentile",
    "rates20_magnitude_bp",
    "rates20_meaningful",
    "rates20_vote_margin",
    "rates5_confirms",
    "rates5_opposes",
    "rates5_percentile",
    "rates60_confirms",
    "rates60_opposes",
    "rates60_percentile",
]

COMBINED_FEATURES_V3181 = list(
    dict.fromkeys(
        COT_STATE_FEATURES_V3181
        + RATES_ONLY_FEATURES_V3181
    )
)

STRICT_LEAD_RELATIONS_V3181 = {
    "CONFLICT",
    "COT_NEUTRAL",
}


def _required_feature_frame_v3181(
    frame: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    out = frame.copy()
    for feature in features:
        if feature not in out.columns:
            out[feature] = np.nan
    return out


def _walk_forward_feature_set_v3181(
    events: pd.DataFrame,
    *,
    target_col: str,
    features: list[str],
    relation_filter: set[str] | None = None,
    min_train_rows: int = MIN_TRAIN_ROWS,
    min_test_rows: int = MIN_TEST_ROWS,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if events is None or events.empty:
        return {
            "target": target_col,
            "oos_n": 0,
            "folds": 0,
            "validation": "INSUFFICIENT DATA",
        }, pd.DataFrame()

    data = events.copy()
    if relation_filter is not None:
        data = data[
            data["relation"].astype(str).isin(relation_filter)
        ].copy()

    data = data.dropna(
        subset=[target_col, "available_date"]
    ).copy()
    if data.empty:
        return {
            "target": target_col,
            "oos_n": 0,
            "folds": 0,
            "validation": "INSUFFICIENT DATA",
        }, pd.DataFrame()

    data = _required_feature_frame_v3181(
        data,
        features,
    )
    data["available_date"] = pd.to_datetime(
        data["available_date"]
    )
    data["year"] = (
        data["available_date"].dt.year.astype(int)
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
            - pd.Timedelta(weeks=PURGE_WEEKS)
        )

        train = data[
            data["available_date"] < train_end
        ].copy()
        test = data[
            (data["available_date"] >= test_start)
            & (data["available_date"] < test_end)
        ].copy()

        if (
            len(train) < int(min_train_rows)
            or len(test) < int(min_test_rows)
            or train[target_col].nunique() < 2
        ):
            continue

        model = _make_model()
        model.fit(
            train[features],
            train[target_col].astype(int),
        )
        probability = model.predict_proba(
            test[features]
        )[:, 1]
        baseline_probability = float(
            train[target_col].mean()
        )

        keep_cols = [
            column
            for column in (
                "currency",
                "available_date",
                "relation",
                target_col,
            )
            if column in test.columns
        ]
        fold = test[keep_cols].copy()
        fold["probability"] = probability
        fold["baseline_probability"] = (
            baseline_probability
        )
        fold["test_year"] = int(test_year)
        oos_rows.append(fold)
        folds += 1

    if not oos_rows:
        metrics = {
            "target": target_col,
            "oos_n": 0,
            "folds": 0,
            "positive_rate": (
                float(data[target_col].mean())
                if len(data)
                else np.nan
            ),
            "brier_model": np.nan,
            "brier_baseline": np.nan,
            "brier_skill": np.nan,
            "roc_auc": np.nan,
            "validation": "INSUFFICIENT DATA",
        }
        return metrics, pd.DataFrame()

    oos = pd.concat(
        oos_rows,
        ignore_index=True,
    )
    y = oos[target_col].astype(int).to_numpy()
    p = oos["probability"].astype(float).to_numpy()
    p0 = oos[
        "baseline_probability"
    ].astype(float).to_numpy()

    brier_model = float(
        brier_score_loss(y, p)
    )
    brier_baseline = float(
        brier_score_loss(y, p0)
    )
    brier_skill = (
        1.0 - brier_model / brier_baseline
        if brier_baseline > 0
        else np.nan
    )
    auc = (
        float(roc_auc_score(y, p))
        if len(np.unique(y)) > 1
        else np.nan
    )

    metrics = {
        "target": target_col,
        "oos_n": int(len(oos)),
        "folds": int(folds),
        "positive_rate": float(np.mean(y)),
        "brier_model": brier_model,
        "brier_baseline": brier_baseline,
        "brier_skill": brier_skill,
        "roc_auc": auc,
    }
    metrics["validation"] = (
        _validation_label(metrics)
    )
    return metrics, oos


def _ablation_study_v3181(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    specs = [
        (
            "Relation only",
            RELATION_ONLY_FEATURES_V3181,
        ),
        (
            "COT-State only",
            COT_STATE_FEATURES_V3181,
        ),
        (
            "Rates only",
            RATES_ONLY_FEATURES_V3181,
        ),
        (
            "COT + Rates",
            COMBINED_FEATURES_V3181,
        ),
    ]

    rows = []
    oos_map: dict[str, pd.DataFrame] = {}

    for name, features in specs:
        metrics, oos = (
            _walk_forward_feature_set_v3181(
                events,
                target_col="transition_6w",
                features=features,
            )
        )
        rows.append(
            {
                "Modell": name,
                **metrics,
            }
        )
        oos_map[name] = oos

    table = pd.DataFrame(rows)
    if table.empty:
        return table, oos_map

    cot = table[
        table["Modell"].eq("COT-State only")
    ]
    cot_brier = (
        _finite(cot.iloc[0]["brier_model"])
        if not cot.empty
        else np.nan
    )
    cot_auc = (
        _finite(cot.iloc[0]["roc_auc"])
        if not cot.empty
        else np.nan
    )

    table["Δ Brier vs COT"] = (
        cot_brier
        - pd.to_numeric(
            table["brier_model"],
            errors="coerce",
        )
    )
    table["Δ AUC vs COT"] = (
        pd.to_numeric(
            table["roc_auc"],
            errors="coerce",
        )
        - cot_auc
    )
    return table, oos_map


def _subset_study_v3181(
    events: pd.DataFrame,
) -> pd.DataFrame:
    specs = [
        (
            "STRICT LEAD · CONFLICT + COT_NEUTRAL",
            {"CONFLICT", "COT_NEUTRAL"},
        ),
        (
            "CONFLICT only",
            {"CONFLICT"},
        ),
        (
            "COT_NEUTRAL only",
            {"COT_NEUTRAL"},
        ),
        (
            "SAME_EXTREME only",
            {"SAME_EXTREME"},
        ),
    ]

    rows = []
    for name, relations in specs:
        subset = events[
            events["relation"]
            .astype(str)
            .isin(relations)
        ].copy()

        metrics, _ = (
            _walk_forward_feature_set_v3181(
                subset,
                target_col="transition_6w",
                features=COMBINED_FEATURES_V3181,
            )
        )
        rows.append(
            {
                "Subset": name,
                "Episoden": int(len(subset)),
                **metrics,
            }
        )

    return pd.DataFrame(rows)


def _sequence_baseline_v3181(
    events: pd.DataFrame,
) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()

    strict = events[
        events["relation"]
        .astype(str)
        .isin(STRICT_LEAD_RELATIONS_V3181)
    ].copy()

    if strict.empty:
        return pd.DataFrame()

    p20 = pd.to_numeric(
        strict["rates20_percentile"],
        errors="coerce",
    )
    r5 = pd.to_numeric(
        strict["rates5_confirms"],
        errors="coerce",
    ).fillna(0).astype(int)
    r60 = pd.to_numeric(
        strict["rates60_confirms"],
        errors="coerce",
    ).fillna(0).astype(int)

    masks = [
        ("STRICT LEAD · alle", pd.Series(True, index=strict.index)),
        ("5D bestätigt", r5.eq(1)),
        ("60D bestätigt", r60.eq(1)),
        ("5D + 60D bestätigen", r5.eq(1) & r60.eq(1)),
        ("20D EXTREME ≥90", p20.ge(90.0)),
        (
            "20D EXTREME + 5D",
            p20.ge(90.0) & r5.eq(1),
        ),
        (
            "20D EXTREME + 5D + 60D",
            p20.ge(90.0)
            & r5.eq(1)
            & r60.eq(1),
        ),
    ]

    rows = []
    for name, mask in masks:
        subset = strict[mask].copy()
        known_t = subset[
            "transition_6w"
        ].dropna()
        known_r = subset[
            "release_8w"
        ].dropna()

        rows.append(
            {
                "Sequenz": name,
                "Episoden": int(len(subset)),
                "Transition ≤6W": (
                    float(known_t.mean())
                    if len(known_t)
                    else np.nan
                ),
                "Release ≤8W": (
                    float(known_r.mean())
                    if len(known_r)
                    else np.nan
                ),
                "Median 20D Pctl": (
                    float(
                        pd.to_numeric(
                            subset["rates20_percentile"],
                            errors="coerce",
                        ).median()
                    )
                    if len(subset)
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


def _oos_group_metrics_v3181(
    oos: pd.DataFrame,
    *,
    target_col: str,
    group_col: str,
) -> pd.DataFrame:
    if oos is None or oos.empty:
        return pd.DataFrame()

    rows = []
    for group, subset in oos.groupby(
        group_col,
        dropna=False,
    ):
        if subset.empty:
            continue

        y = subset[
            target_col
        ].astype(int).to_numpy()
        p = subset[
            "probability"
        ].astype(float).to_numpy()
        p0 = subset[
            "baseline_probability"
        ].astype(float).to_numpy()

        brier_model = float(
            brier_score_loss(y, p)
        )
        brier_baseline = float(
            brier_score_loss(y, p0)
        )
        brier_skill = (
            1.0
            - brier_model / brier_baseline
            if brier_baseline > 0
            else np.nan
        )
        auc = (
            float(roc_auc_score(y, p))
            if len(np.unique(y)) > 1
            else np.nan
        )

        rows.append(
            {
                group_col: group,
                "n": int(len(subset)),
                "Basisrate": float(np.mean(y)),
                "Brier ML": brier_model,
                "Brier Basis": brier_baseline,
                "Brier Skill": brier_skill,
                "ROC-AUC": auc,
            }
        )

    return pd.DataFrame(rows)


def _time_aware_loco_v3181(
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Held currency never appears in training.

    For each held currency and each test year:
      train = other currencies only AND strictly before the test year purge
      test  = held currency in that test year

    This is intentionally stricter than ordinary per-currency OOS reporting.
    """
    if events is None or events.empty:
        return pd.DataFrame()

    data = events.dropna(
        subset=["transition_6w", "available_date"]
    ).copy()
    if data.empty:
        return pd.DataFrame()

    data = _required_feature_frame_v3181(
        data,
        COMBINED_FEATURES_V3181,
    )
    data["available_date"] = pd.to_datetime(
        data["available_date"]
    )
    data["year"] = (
        data["available_date"].dt.year.astype(int)
    )

    oos_rows = []

    for held_currency in sorted(
        data["currency"].astype(str).unique()
    ):
        held = data[
            data["currency"]
            .astype(str)
            .eq(str(held_currency))
        ].copy()

        for test_year in sorted(
            held["year"].unique().tolist()
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
                - pd.Timedelta(weeks=PURGE_WEEKS)
            )

            train = data[
                (~data["currency"].astype(str).eq(str(held_currency)))
                & (data["available_date"] < train_end)
            ].copy()
            test = held[
                (held["available_date"] >= test_start)
                & (held["available_date"] < test_end)
            ].copy()

            if (
                len(train) < MIN_TRAIN_ROWS
                or len(test) < 1
                or train["transition_6w"].nunique() < 2
            ):
                continue

            model = _make_model()
            model.fit(
                train[COMBINED_FEATURES_V3181],
                train["transition_6w"].astype(int),
            )
            probability = model.predict_proba(
                test[COMBINED_FEATURES_V3181]
            )[:, 1]

            fold = test[
                [
                    "currency",
                    "available_date",
                    "transition_6w",
                ]
            ].copy()
            fold["probability"] = probability
            fold["baseline_probability"] = float(
                train["transition_6w"].mean()
            )
            fold["test_year"] = int(test_year)
            oos_rows.append(fold)

    if not oos_rows:
        return pd.DataFrame()

    oos = pd.concat(
        oos_rows,
        ignore_index=True,
    )
    return _oos_group_metrics_v3181(
        oos,
        target_col="transition_6w",
        group_col="currency",
    )


def _incremental_read_v3181(
    ablation: pd.DataFrame,
) -> dict[str, Any]:
    if ablation is None or ablation.empty:
        return {
            "label": "INSUFFICIENT DATA",
            "text": (
                "Noch nicht genügend vergleichbare OOS-Daten "
                "für die Feature-Ablation."
            ),
        }

    cot = ablation[
        ablation["Modell"].eq("COT-State only")
    ]
    combined = ablation[
        ablation["Modell"].eq("COT + Rates")
    ]
    relation = ablation[
        ablation["Modell"].eq("Relation only")
    ]

    if cot.empty or combined.empty:
        return {
            "label": "INSUFFICIENT DATA",
            "text": "COT- oder Combined-Referenz fehlt.",
        }

    cot_brier = _finite(
        cot.iloc[0].get("brier_model")
    )
    cot_auc = _finite(
        cot.iloc[0].get("roc_auc")
    )
    combined_brier = _finite(
        combined.iloc[0].get("brier_model")
    )
    combined_auc = _finite(
        combined.iloc[0].get("roc_auc")
    )

    brier_gain = (
        cot_brier - combined_brier
        if np.isfinite(cot_brier)
        and np.isfinite(combined_brier)
        else np.nan
    )
    auc_gain = (
        combined_auc - cot_auc
        if np.isfinite(cot_auc)
        and np.isfinite(combined_auc)
        else np.nan
    )

    relation_auc = (
        _finite(relation.iloc[0].get("roc_auc"))
        if not relation.empty
        else np.nan
    )

    dominated_by_relation = (
        np.isfinite(relation_auc)
        and np.isfinite(combined_auc)
        and abs(combined_auc - relation_auc) <= 0.02
    )

    if (
        np.isfinite(brier_gain)
        and np.isfinite(auc_gain)
        and brier_gain > 0.01
        and auc_gain >= 0.03
    ):
        label = "RATES ADD INCREMENTAL OOS INFORMATION"
    elif (
        np.isfinite(brier_gain)
        and brier_gain > 0
        and np.isfinite(auc_gain)
        and auc_gain > 0
    ):
        label = "SMALL INCREMENTAL RATES VALUE"
    else:
        label = "NO CLEAR INCREMENTAL RATES VALUE"

    if dominated_by_relation:
        label += " · RELATION DOMINATES"

    return {
        "label": label,
        "brier_gain_vs_cot": brier_gain,
        "auc_gain_vs_cot": auc_gain,
        "relation_dominates": dominated_by_relation,
        "text": (
            "Verglichen wird auf exakt denselben Rates-Episoden. "
            "Damit testen wir, ob Rates-Stärke und 5D/60D-Bestätigung "
            "über den aktuellen COT-Zustand hinaus zusätzliche "
            "Out-of-Sample-Information liefern."
        ),
    }


_run_rates_cot_ml_study_v3180 = run_rates_cot_ml_study


def run_rates_cot_ml_study() -> dict[str, Any]:
    """V3.18.1: extend V3.18.0 with strict ablation and robustness."""
    result = _run_rates_cot_ml_study_v3180()
    events = result.get("events", pd.DataFrame())

    ablation, ablation_oos = (
        _ablation_study_v3181(events)
    )
    combined_oos = ablation_oos.get(
        "COT + Rates",
        pd.DataFrame(),
    )

    result["ablation"] = ablation
    result["incremental_read"] = (
        _incremental_read_v3181(ablation)
    )
    result["strict_subsets"] = (
        _subset_study_v3181(events)
    )
    result["sequence_baseline"] = (
        _sequence_baseline_v3181(events)
    )
    result["stability_by_year"] = (
        _oos_group_metrics_v3181(
            combined_oos,
            target_col="transition_6w",
            group_col="test_year",
        )
    )
    result["stability_by_currency"] = (
        _oos_group_metrics_v3181(
            combined_oos,
            target_col="transition_6w",
            group_col="currency",
        )
    )
    result["leave_one_currency_out"] = (
        _time_aware_loco_v3181(events)
    )

    return result
