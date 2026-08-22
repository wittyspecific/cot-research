
from pathlib import Path

import pandas as pd

from src.macro.config import load_config
from src.macro.features import build_feature_library


def _monthly(values):
    dates = pd.date_range(
        "2020-01-01",
        periods=len(values),
        freq="MS",
    )
    return pd.DataFrame(
        {
            "observation_date": dates,
            "availability_date": dates
            + pd.to_timedelta(40, unit="D"),
            "value": values,
        }
    )


def test_payroll_feature_uses_native_monthly_change_not_weekly_diff():
    cfg = load_config(
        Path("/definitely/missing.toml")
    )

    values = [
        100.0,
        110.0,
        130.0,
        160.0,
        200.0,
        250.0,
        310.0,
        380.0,
        460.0,
        550.0,
        650.0,
        760.0,
        880.0,
        1010.0,
        1150.0,
        1300.0,
        1460.0,
        1630.0,
        1810.0,
        2000.0,
        2200.0,
        2410.0,
        2630.0,
        2860.0,
        3100.0,
        3350.0,
        3610.0,
        3880.0,
        4160.0,
        4450.0,
        4750.0,
        5060.0,
        5380.0,
        5710.0,
        6050.0,
        6400.0,
        6760.0,
        7130.0,
        7510.0,
        7900.0,
    ]

    features = build_feature_library(
        {
            "payems": _monthly(values),
        },
        cfg,
    )

    payroll = features[
        "Payroll Monthly Change"
    ].frame

    raw = payroll["raw"].dropna()
    assert raw.iloc[-1] == 390.0


def test_future_release_is_not_available_before_availability_date():
    from src.macro.features import (
        align_features_weekly,
    )

    cfg = load_config(
        Path("/definitely/missing.toml")
    )

    frame = _monthly(
        [100 + i for i in range(60)]
    )
    features = build_feature_library(
        {"payems": frame},
        cfg,
    )

    scores, _ = align_features_weekly(
        features,
        as_of="2024-12-20",
    )

    # Last observation in the raw data must never be usable before its
    # conservative availability date.
    assert scores.index.max() <= pd.Timestamp("2024-12-20")
