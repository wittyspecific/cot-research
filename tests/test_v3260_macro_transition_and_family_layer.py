from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.macro.transition_models import (
    evaluate_transition_layer,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "src" / "macro" / "config.py"
ENGINE = ROOT / "src" / "macro" / "macro_model_library.py"
TYPES = ROOT / "src" / "macro" / "types.py"
PAGE = ROOT / "pages" / "macro_model_library.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _monthly(
    values,
    *,
    start="2018-01-01",
    lag=40,
):
    dates = pd.date_range(
        start,
        periods=len(values),
        freq="MS",
    )

    return pd.DataFrame(
        {
            "observation_date": dates,
            "availability_date": (
                dates
                + pd.to_timedelta(
                    lag,
                    unit="D",
                )
            ),
            "value": values,
        }
    )


def _daily_rates(values):
    dates = pd.date_range(
        "2018-01-01",
        periods=len(values),
        freq="W-FRI",
    )

    return pd.DataFrame(
        {
            "observation_date": dates,
            "availability_date": (
                dates
                + pd.to_timedelta(
                    1,
                    unit="D",
                )
            ),
            "value": values,
        }
    )


def _fixture():
    n = 96

    labor_force = np.linspace(
        160_000,
        168_000,
        n,
    )

    employment = np.linspace(
        154_000,
        160_500,
        n,
    )

    full_time = np.linspace(
        126_000,
        132_000,
        n,
    )

    population = np.linspace(
        258_000,
        272_000,
        n,
    )

    permits = np.concatenate(
        [
            np.linspace(
                1200,
                1800,
                n - 12,
            ),
            np.linspace(
                1750,
                1350,
                12,
            ),
        ]
    )

    starts = np.concatenate(
        [
            np.linspace(
                1100,
                1700,
                n - 12,
            ),
            np.linspace(
                1650,
                1250,
                12,
            ),
        ]
    )

    dpi = np.linspace(
        14_000,
        18_000,
        n,
    )

    pce = np.linspace(
        13_000,
        17_000,
        n,
    )

    earnings = np.linspace(
        25,
        38,
        n,
    )

    cpi = np.linspace(
        250,
        320,
        n,
    )

    saving = np.linspace(
        6,
        4,
        n,
    )

    us2y = np.concatenate(
        [
            np.linspace(
                1.0,
                5.0,
                70,
            ),
            np.linspace(
                5.0,
                3.2,
                26,
            ),
        ]
    )

    series = {
        "labor_force": _monthly(
            labor_force
        ),
        "civilian_employment": _monthly(
            employment
        ),
        "full_time_employment": _monthly(
            full_time
        ),
        "civilian_population": _monthly(
            population
        ),
        "building_permits": _monthly(
            permits,
            lag=50,
        ),
        "housing_starts": _monthly(
            starts,
            lag=50,
        ),
        "real_disposable_income": _monthly(
            dpi,
            lag=45,
        ),
        "real_pce": _monthly(
            pce,
            lag=45,
        ),
        "personal_saving_rate": _monthly(
            saving,
            lag=45,
        ),
        "avg_hourly_earnings": _monthly(
            earnings,
        ),
        "cpi": _monthly(
            cpi,
            lag=20,
        ),
        "us2y": _daily_rates(
            us2y
        ),
    }

    idx = pd.date_range(
        "2025-06-06",
        periods=60,
        freq="W-FRI",
    )

    cycle = pd.DataFrame(
        {
            "coincident_slope_13w": (
                np.linspace(
                    5.0,
                    -8.0,
                    len(idx),
                )
            ),
            "cycle_phase": [
                "SLOWDOWN"
            ]
            * len(idx),
        },
        index=idx,
    )

    scores = pd.DataFrame(
        {
            "Initial Claims 4W": [
                -35.0
            ]
            * len(idx),
            "Initial Claims 13W": [
                -30.0
            ]
            * len(idx),
            "Continuing Claims 13W": [
                -25.0
            ]
            * len(idx),
        },
        index=idx,
    )

    return (
        series,
        cycle,
        scores,
    )


def test_transition_layer_exposes_three_families_and_three_transitions():
    (
        series,
        cycle,
        scores,
    ) = _fixture()

    result = evaluate_transition_layer(
        series_map=series,
        cycle_history=cycle,
        weekly_scores=scores,
    )

    assert result[
        "mode"
    ] == "DIAGNOSTIC_ONLY_NO_CYCLE_VOTE"

    assert set(
        result[
            "families"
        ]
    ) == {
        "labor_quality",
        "housing_activity",
        "household_resilience",
    }

    assert set(
        result[
            "transitions"
        ]
    ) == {
        "housing_to_labor",
        "labor_to_household",
        "coincident_to_2y",
    }


def test_new_macro_series_are_optional_and_do_not_enter_core_feature_library():
    text = CONFIG.read_text(
        encoding="utf-8"
    )

    for token in (
        '"labor_force"',
        '"civilian_employment"',
        '"full_time_employment"',
        '"civilian_population"',
        '"real_disposable_income"',
        '"real_pce"',
        '"personal_saving_rate"',
        '"avg_hourly_earnings"',
    ):
        assert token in text

    diagnostic_block = text[
        text.index(
            "# V3.26.0 diagnostic macro families"
        ):
        text.index(
            "DEFAULT_CONFIG"
        )
    ]

    assert diagnostic_block.count(
        "required=False"
    ) >= 8

    features = (
        ROOT
        / "src"
        / "macro"
        / "features.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "full_time_employment",
        "real_disposable_income",
        "personal_saving_rate",
    ):
        assert token not in features


def test_engine_calculates_cycle_before_transition_diagnostics():
    text = ENGINE.read_text(
        encoding="utf-8"
    )

    cycle_pos = text.index(
        "cycle_phase ="
    )

    transition_pos = text.index(
        "transition_layer = evaluate_transition_layer"
    )

    assert cycle_pos < transition_pos

    assert (
        "cycle_phase = transition_layer"
        not in text
    )


def test_result_exposes_transition_models_and_macro_families():
    types = TYPES.read_text(
        encoding="utf-8"
    )

    engine = ENGINE.read_text(
        encoding="utf-8"
    )

    assert (
        "transition_models: dict[str, Any]"
        in types
    )

    assert (
        "macro_families: dict[str, Any]"
        in types
    )

    assert (
        'transition_models=transition_layer["transitions"]'
        in engine
    )

    assert (
        'macro_families=transition_layer["families"]'
        in engine
    )


def test_page_shows_transition_layer_and_family_roles():
    text = PAGE.read_text(
        encoding="utf-8"
    )

    for token in (
        "Transition Models & Macro Families",
        "LABOR QUALITY",
        "HOUSING ACTIVITY",
        "HOUSEHOLD RESILIENCE",
        "HOUSING → LABOR",
        "LABOR → HOUSEHOLD",
        "COINCIDENT → US 2Y",
        "kein zusätzlicher Cycle Vote",
    ):
        assert token.lower() in text.lower()


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(
        encoding="utf-8"
    )

    assert (
        "transition_models"
        not in text
    )

    assert (
        "labor_quality"
        not in text
    )


def test_python_files_parse():
    for path in (
        ROOT
        / "src"
        / "macro"
        / "transition_models.py",
        CONFIG,
        TYPES,
        ENGINE,
        PAGE,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
