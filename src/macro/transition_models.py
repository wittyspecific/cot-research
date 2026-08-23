from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _num(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _available_frame(
    series_map: dict[str, pd.DataFrame],
    key: str,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    frame = series_map.get(key)

    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=[
                "observation_date",
                "availability_date",
                "value",
            ]
        )

    work = frame[
        [
            "observation_date",
            "availability_date",
            "value",
        ]
    ].copy()

    work["observation_date"] = pd.to_datetime(
        work["observation_date"],
        errors="coerce",
    )
    work["availability_date"] = pd.to_datetime(
        work["availability_date"],
        errors="coerce",
    )
    work["value"] = pd.to_numeric(
        work["value"],
        errors="coerce",
    )

    work = work.dropna(
        subset=[
            "observation_date",
            "availability_date",
            "value",
        ]
    )

    work = work.loc[
        work["availability_date"]
        <= pd.Timestamp(as_of)
    ].sort_values(
        "observation_date"
    )

    return work.reset_index(
        drop=True
    )


def _monthly(
    series_map: dict[str, pd.DataFrame],
    key: str,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    frame = _available_frame(
        series_map,
        key,
        as_of,
    )

    if frame.empty:
        return frame

    frame = frame.copy()
    frame["period"] = frame[
        "observation_date"
    ].dt.to_period(
        "M"
    )

    frame = (
        frame.groupby(
            "period",
            as_index=False,
        )
        .tail(1)
        .sort_values(
            "observation_date"
        )
        .reset_index(
            drop=True
        )
    )

    return frame


def _merge_monthly(
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> pd.DataFrame:
    if left.empty or right.empty:
        return pd.DataFrame()

    a = left[
        [
            "period",
            "observation_date",
            "availability_date",
            "value",
        ]
    ].rename(
        columns={
            "observation_date": "left_date",
            "availability_date": "left_availability",
            "value": "left_value",
        }
    )

    b = right[
        [
            "period",
            "observation_date",
            "availability_date",
            "value",
        ]
    ].rename(
        columns={
            "observation_date": "right_date",
            "availability_date": "right_availability",
            "value": "right_value",
        }
    )

    merged = a.merge(
        b,
        on="period",
        how="inner",
    )

    if merged.empty:
        return merged

    merged["availability_date"] = pd.concat(
        [
            merged["left_availability"],
            merged["right_availability"],
        ],
        axis=1,
    ).max(
        axis=1
    )

    return merged.sort_values(
        "period"
    ).reset_index(
        drop=True
    )


def _direction(
    value: float | None,
    *,
    threshold: float = 0.0,
) -> int | None:
    if value is None:
        return None

    if value > abs(
        float(threshold)
    ):
        return 1

    if value < -abs(
        float(threshold)
    ):
        return -1

    return 0


def _ratio_component(
    *,
    series_map: dict[str, pd.DataFrame],
    numerator: str,
    denominator: str,
    as_of: pd.Timestamp,
    label: str,
    periods: int = 6,
    threshold_pp: float = 0.02,
) -> dict[str, Any]:
    merged = _merge_monthly(
        _monthly(
            series_map,
            numerator,
            as_of,
        ),
        _monthly(
            series_map,
            denominator,
            as_of,
        ),
    )

    if merged.empty:
        return {
            "label": label,
            "value": None,
            "change": None,
            "direction": None,
            "unit": "%",
        }

    ratio = (
        merged["left_value"]
        / merged["right_value"].replace(
            0,
            np.nan,
        )
        * 100.0
    )

    change = ratio.diff(
        int(periods)
    )

    value_now = _num(
        ratio.iloc[-1]
    )
    change_now = _num(
        change.iloc[-1]
    )

    return {
        "label": label,
        "value": value_now,
        "change": change_now,
        "direction": _direction(
            change_now,
            threshold=threshold_pp,
        ),
        "unit": "%",
        "change_unit": "pp/6M",
    }


def _normalized_housing_component(
    *,
    series_map: dict[str, pd.DataFrame],
    activity_key: str,
    as_of: pd.Timestamp,
    label: str,
) -> dict[str, Any]:
    merged = _merge_monthly(
        _monthly(
            series_map,
            activity_key,
            as_of,
        ),
        _monthly(
            series_map,
            "civilian_population",
            as_of,
        ),
    )

    if merged.empty:
        return {
            "label": label,
            "value": None,
            "change": None,
            "direction": None,
            "unit": "per 1k population",
        }

    normalized = (
        merged["left_value"]
        / merged["right_value"].replace(
            0,
            np.nan,
        )
        * 1000.0
    )

    change_6m = normalized.pct_change(
        6,
        fill_method=None,
    ) * 100.0

    value_now = _num(
        normalized.iloc[-1]
    )
    change_now = _num(
        change_6m.iloc[-1]
    )

    return {
        "label": label,
        "value": value_now,
        "change": change_now,
        "direction": _direction(
            change_now,
            threshold=2.0,
        ),
        "unit": "per 1k population",
        "change_unit": "%/6M",
    }


def _growth_component(
    *,
    series_map: dict[str, pd.DataFrame],
    key: str,
    as_of: pd.Timestamp,
    label: str,
    periods: int = 12,
    threshold_pct: float = 0.0,
) -> dict[str, Any]:
    frame = _monthly(
        series_map,
        key,
        as_of,
    )

    if frame.empty:
        return {
            "label": label,
            "value": None,
            "change": None,
            "direction": None,
            "unit": "%",
        }

    values = pd.to_numeric(
        frame["value"],
        errors="coerce",
    )

    growth = values.pct_change(
        int(periods),
        fill_method=None,
    ) * 100.0

    value_now = _num(
        values.iloc[-1]
    )
    growth_now = _num(
        growth.iloc[-1]
    )

    return {
        "label": label,
        "value": value_now,
        "change": growth_now,
        "direction": _direction(
            growth_now,
            threshold=threshold_pct,
        ),
        "unit": "level",
        "change_unit": "% YoY",
    }


def _real_wage_component(
    *,
    series_map: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
) -> dict[str, Any]:
    merged = _merge_monthly(
        _monthly(
            series_map,
            "avg_hourly_earnings",
            as_of,
        ),
        _monthly(
            series_map,
            "cpi",
            as_of,
        ),
    )

    if merged.empty:
        return {
            "label": "Real Hourly Earnings YoY",
            "value": None,
            "change": None,
            "direction": None,
            "unit": "real index",
        }

    real_wage = (
        merged["left_value"]
        / merged["right_value"].replace(
            0,
            np.nan,
        )
        * 100.0
    )

    growth = real_wage.pct_change(
        12,
        fill_method=None,
    ) * 100.0

    growth_now = _num(
        growth.iloc[-1]
    )

    return {
        "label": "Real Hourly Earnings YoY",
        "value": _num(
            real_wage.iloc[-1]
        ),
        "change": growth_now,
        "direction": _direction(
            growth_now,
            threshold=0.0,
        ),
        "unit": "real index",
        "change_unit": "% YoY",
    }


def _saving_context(
    *,
    series_map: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
) -> dict[str, Any]:
    frame = _monthly(
        series_map,
        "personal_saving_rate",
        as_of,
    )

    if frame.empty:
        return {
            "label": "Personal Saving Rate",
            "value": None,
            "change": None,
            "direction": None,
            "unit": "%",
            "vote": False,
        }

    values = pd.to_numeric(
        frame["value"],
        errors="coerce",
    )

    delta = values.diff(
        6
    )

    return {
        "label": "Personal Saving Rate",
        "value": _num(
            values.iloc[-1]
        ),
        "change": _num(
            delta.iloc[-1]
        ),
        "direction": None,
        "unit": "%",
        "change_unit": "pp/6M",
        "vote": False,
        "note": (
            "Buffer context only: a rising saving rate can reflect resilience "
            "or defensive behavior, so it does not vote mechanically."
        ),
    }


def _family_summary(
    name: str,
    label: str,
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    voters = [
        item
        for item in components
        if item.get(
            "vote",
            True,
        )
        and item.get(
            "direction"
        )
        is not None
    ]

    available = len(
        voters
    )

    positive = sum(
        int(
            item.get(
                "direction"
            )
            == 1
        )
        for item in voters
    )

    negative = sum(
        int(
            item.get(
                "direction"
            )
            == -1
        )
        for item in voters
    )

    neutral = sum(
        int(
            item.get(
                "direction"
            )
            == 0
        )
        for item in voters
    )

    if available == 0:
        state = "N/V"
        positive_share = None
        negative_share = None
    else:
        positive_share = (
            positive
            / available
        )
        negative_share = (
            negative
            / available
        )

        if (
            positive_share
            >= 0.67
        ):
            state = "STRENGTHENING"
        elif (
            negative_share
            >= 0.67
        ):
            state = "WEAKENING"
        else:
            state = "MIXED"

    return {
        "key": name,
        "label": label,
        "state": state,
        "positive_components": int(
            positive
        ),
        "negative_components": int(
            negative
        ),
        "neutral_components": int(
            neutral
        ),
        "available_components": int(
            available
        ),
        "positive_breadth": positive_share,
        "negative_breadth": negative_share,
        "components": components,
        "role": "DIAGNOSTIC_ONLY_NO_CYCLE_VOTE",
    }


def _latest_score(
    weekly_scores: pd.DataFrame,
    names: tuple[str, ...],
) -> float | None:
    if (
        weekly_scores is None
        or weekly_scores.empty
    ):
        return None

    values = []

    row = weekly_scores.iloc[
        -1
    ]

    for name in names:
        if name not in weekly_scores.columns:
            continue

        value = _num(
            row.get(
                name
            )
        )

        if value is not None:
            values.append(
                value
            )

    return (
        float(
            np.mean(
                values
            )
        )
        if values
        else None
    )


def _us2y_change_13w(
    series_map: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
) -> float | None:
    frame = _available_frame(
        series_map,
        "us2y",
        as_of,
    )

    if frame.empty:
        return None

    work = frame.copy()
    work["period"] = work[
        "observation_date"
    ].dt.to_period(
        "W-FRI"
    )

    work = (
        work.groupby(
            "period",
            as_index=False,
        )
        .tail(1)
        .sort_values(
            "observation_date"
        )
    )

    values = pd.to_numeric(
        work["value"],
        errors="coerce",
    )

    delta = values.diff(
        13
    )

    return (
        _num(
            delta.iloc[-1]
        )
        if not delta.empty
        else None
    )


def _housing_to_labor(
    *,
    housing: dict[str, Any],
    labor: dict[str, Any],
    claims_score: float | None,
) -> dict[str, Any]:
    h = housing.get(
        "state",
        "N/V",
    )
    l = labor.get(
        "state",
        "N/V",
    )

    claims_weak = (
        claims_score is not None
        and claims_score < -20.0
    )

    claims_ok = (
        claims_score is not None
        and claims_score >= -20.0
    )

    if (
        h == "WEAKENING"
        and (
            l == "WEAKENING"
            or claims_weak
        )
    ):
        state = "TRANSMISSION_CONFIRMED"
        interpretation = (
            "Housing weakness is already accompanied by labor deterioration."
        )
    elif (
        h == "WEAKENING"
        and (
            l in {
                "STRENGTHENING",
                "MIXED",
            }
            or claims_ok
        )
    ):
        state = "HOUSING_LEADS_WEAKNESS"
        interpretation = (
            "Housing is weakening while labor has not fully followed yet."
        )
    elif (
        h == "STRENGTHENING"
        and (
            l == "WEAKENING"
            or claims_weak
        )
    ):
        state = "HOUSING_LEADS_RECOVERY"
        interpretation = (
            "Housing is improving while labor remains weak, a possible recovery lead."
        )
    elif (
        h == "STRENGTHENING"
        and l == "STRENGTHENING"
        and not claims_weak
    ):
        state = "BROAD_EXPANSION"
        interpretation = (
            "Housing and labor are broadly aligned on the stronger side."
        )
    else:
        state = "MIXED"
        interpretation = (
            "Housing and labor do not form a clean transition sequence."
        )

    return {
        "key": "housing_to_labor",
        "label": "Housing → Labor",
        "state": state,
        "interpretation": interpretation,
        "evidence": {
            "housing_state": h,
            "labor_quality_state": l,
            "claims_score": claims_score,
        },
        "role": "TRANSITION_DIAGNOSTIC_ONLY",
    }


def _labor_to_household(
    *,
    labor: dict[str, Any],
    household: dict[str, Any],
) -> dict[str, Any]:
    l = labor.get(
        "state",
        "N/V",
    )
    h = household.get(
        "state",
        "N/V",
    )

    if (
        l == "WEAKENING"
        and h == "STRENGTHENING"
    ):
        state = "HOUSEHOLD_BUFFER"
        interpretation = (
            "Labor is weakening but household income/consumption resilience is still cushioning demand."
        )
    elif (
        l == "WEAKENING"
        and h == "WEAKENING"
    ):
        state = "DEMAND_TRANSMISSION_CONFIRMED"
        interpretation = (
            "Labor weakness is transmitting into household resilience and demand."
        )
    elif (
        l == "STRENGTHENING"
        and h == "WEAKENING"
    ):
        state = "HOUSEHOLD_LAG"
        interpretation = (
            "Labor is improving before household resilience has recovered."
        )
    elif (
        l == "STRENGTHENING"
        and h == "STRENGTHENING"
    ):
        state = "BROAD_RESILIENCE"
        interpretation = (
            "Labor quality and household resilience are aligned on the stronger side."
        )
    else:
        state = "MIXED"
        interpretation = (
            "Labor and household conditions do not form a clean transition sequence."
        )

    return {
        "key": "labor_to_household",
        "label": "Labor → Household",
        "state": state,
        "interpretation": interpretation,
        "evidence": {
            "labor_quality_state": l,
            "household_state": h,
        },
        "role": "TRANSITION_DIAGNOSTIC_ONLY",
    }


def _coincident_to_2y(
    *,
    cycle_history: pd.DataFrame,
    us2y_change_13w: float | None,
) -> dict[str, Any]:
    coincident_slope = None

    if (
        cycle_history is not None
        and not cycle_history.empty
        and "coincident_slope_13w"
        in cycle_history.columns
    ):
        coincident_slope = _num(
            cycle_history.iloc[
                -1
            ].get(
                "coincident_slope_13w"
            )
        )

    if (
        coincident_slope is None
        or us2y_change_13w is None
    ):
        state = "N/V"
        interpretation = (
            "Insufficient coincident or US 2Y data for transition read."
        )
    elif (
        coincident_slope < -2.0
        and us2y_change_13w <= -0.25
    ):
        state = "GROWTH_WEAKNESS_CONFIRMED_BY_2Y"
        interpretation = (
            "Coincident growth is rolling over and the US 2Y yield is already falling."
        )
    elif (
        coincident_slope < -2.0
        and us2y_change_13w > -0.25
    ):
        state = "2Y_LAGGING_GROWTH_SLOWDOWN"
        interpretation = (
            "Coincident growth is weakening while the US 2Y has not materially followed yet."
        )
    elif (
        coincident_slope > 2.0
        and us2y_change_13w >= 0.25
    ):
        state = "REACCELERATION_CONFIRMED_BY_2Y"
        interpretation = (
            "Coincident growth and the US 2Y are aligned on reacceleration."
        )
    elif (
        coincident_slope > 2.0
        and us2y_change_13w < 0.25
    ):
        state = "2Y_LAGGING_RECOVERY"
        interpretation = (
            "Coincident growth is improving before the US 2Y has clearly followed."
        )
    else:
        state = "MIXED"
        interpretation = (
            "Coincident growth and the US 2Y do not show a clean directional sequence."
        )

    return {
        "key": "coincident_to_2y",
        "label": "Coincident → US 2Y",
        "state": state,
        "interpretation": interpretation,
        "evidence": {
            "coincident_slope_13w": coincident_slope,
            "us2y_change_13w_pp": us2y_change_13w,
        },
        "role": "TRANSITION_DIAGNOSTIC_ONLY",
    }


def evaluate_transition_layer(
    *,
    series_map: dict[str, pd.DataFrame],
    cycle_history: pd.DataFrame,
    weekly_scores: pd.DataFrame,
) -> dict[str, Any]:
    """
    Transparent research-only transition layer.

    It does NOT modify cycle_phase, transition_state, breadth, imminent recession,
    or liquidity. The rules are public proxies and are not Henrik Zeberg's
    proprietary formulas or weights.
    """

    if (
        cycle_history is None
        or cycle_history.empty
    ):
        return {
            "families": {},
            "transitions": {},
            "as_of": None,
            "mode": "DIAGNOSTIC_ONLY_NO_CYCLE_VOTE",
        }

    as_of = pd.Timestamp(
        cycle_history.index.max()
    )

    labor_components = [
        _ratio_component(
            series_map=series_map,
            numerator="full_time_employment",
            denominator="labor_force",
            as_of=as_of,
            label="Full-Time / Labor Force",
        ),
        _ratio_component(
            series_map=series_map,
            numerator="civilian_employment",
            denominator="labor_force",
            as_of=as_of,
            label="Employment / Labor Force",
        ),
        _ratio_component(
            series_map=series_map,
            numerator="civilian_employment",
            denominator="civilian_population",
            as_of=as_of,
            label="Employment / Population",
        ),
        _ratio_component(
            series_map=series_map,
            numerator="full_time_employment",
            denominator="civilian_employment",
            as_of=as_of,
            label="Full-Time / Employment",
        ),
    ]

    labor = _family_summary(
        "labor_quality",
        "Labor Quality",
        labor_components,
    )

    housing_components = [
        _normalized_housing_component(
            series_map=series_map,
            activity_key="building_permits",
            as_of=as_of,
            label="Permits / Population",
        ),
        _normalized_housing_component(
            series_map=series_map,
            activity_key="housing_starts",
            as_of=as_of,
            label="Starts / Population",
        ),
    ]

    housing = _family_summary(
        "housing_activity",
        "Housing Activity Normalization",
        housing_components,
    )

    household_components = [
        _growth_component(
            series_map=series_map,
            key="real_disposable_income",
            as_of=as_of,
            label="Real Disposable Income YoY",
            threshold_pct=0.0,
        ),
        _growth_component(
            series_map=series_map,
            key="real_pce",
            as_of=as_of,
            label="Real Consumption YoY",
            threshold_pct=0.0,
        ),
        _real_wage_component(
            series_map=series_map,
            as_of=as_of,
        ),
        _saving_context(
            series_map=series_map,
            as_of=as_of,
        ),
    ]

    household = _family_summary(
        "household_resilience",
        "Household Resilience",
        household_components,
    )

    claims_score = _latest_score(
        weekly_scores,
        (
            "Initial Claims 4W",
            "Initial Claims 13W",
            "Continuing Claims 13W",
        ),
    )

    us2y_delta = _us2y_change_13w(
        series_map,
        as_of,
    )

    transitions = {
        "housing_to_labor": _housing_to_labor(
            housing=housing,
            labor=labor,
            claims_score=claims_score,
        ),
        "labor_to_household": _labor_to_household(
            labor=labor,
            household=household,
        ),
        "coincident_to_2y": _coincident_to_2y(
            cycle_history=cycle_history,
            us2y_change_13w=us2y_delta,
        ),
    }

    families = {
        "labor_quality": labor,
        "housing_activity": housing,
        "household_resilience": household,
    }

    return {
        "as_of": as_of.date().isoformat(),
        "mode": "DIAGNOSTIC_ONLY_NO_CYCLE_VOTE",
        "families": families,
        "transitions": transitions,
        "limitations": [
            "Current/revised FRED history with conservative release lags; not true vintage/PIT.",
            "Population-normalized housing is an activity proxy, not a direct home-demand survey.",
            "Personal saving rate is context only and does not mechanically vote.",
            "Transition states are transparent heuristic diagnostics and require historical validation before calibration.",
            "No proprietary Henrik Zeberg formula, weight or equilibrium construction is replicated.",
        ],
    }
