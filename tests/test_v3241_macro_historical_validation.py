from pathlib import Path
import ast

import pandas as pd
import pytest

from src.macro.historical_validation import (
    evaluate_historical_cycle,
    recession_episodes_from_usrec,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "macro" / "macro_model_library.py"
PAGE = ROOT / "pages" / "macro_model_library.py"
CONFIG = ROOT / "src" / "macro" / "config.py"
TOML = ROOT / "config" / "macro_model_library.toml"
WATCH = ROOT / "pages" / "watchlist.py"


def _usrec():
    dates = pd.date_range(
        "1989-01-01",
        "2021-12-01",
        freq="MS",
    )
    values = pd.Series(0.0, index=dates)

    for start, end in (
        ("1990-07-01", "1991-03-01"),
        ("2001-03-01", "2001-11-01"),
        ("2007-12-01", "2009-06-01"),
        ("2020-02-01", "2020-04-01"),
    ):
        values.loc[
            pd.Timestamp(start):
            pd.Timestamp(end)
        ] = 1.0

    return pd.DataFrame(
        {
            "observation_date": dates,
            "value": values.values,
        }
    )


def test_extracts_four_post_1990_recession_episodes():
    episodes = recession_episodes_from_usrec(
        _usrec(),
        start_year=1990,
    )

    assert [
        episode.start.date().isoformat()
        for episode in episodes
    ] == [
        "1990-07-01",
        "2001-03-01",
        "2007-12-01",
        "2020-02-01",
    ]


def test_historical_validation_measures_lead_lag():
    idx = pd.date_range(
        "1989-01-06",
        "2021-12-31",
        freq="W-FRI",
    )
    phase = pd.Series("EXPANSION", index=idx)

    recessions = [
        (pd.Timestamp("1990-07-01"), pd.Timestamp("1991-03-31")),
        (pd.Timestamp("2001-03-01"), pd.Timestamp("2001-11-30")),
        (pd.Timestamp("2007-12-01"), pd.Timestamp("2009-06-30")),
        (pd.Timestamp("2020-02-01"), pd.Timestamp("2020-04-30")),
    ]

    for start, end in recessions:
        phase.loc[
            (phase.index >= start - pd.Timedelta(weeks=20))
            & (phase.index < start)
        ] = "SLOWDOWN"
        phase.loc[
            (phase.index >= start)
            & (phase.index <= end)
        ] = "CONTRACTION"
        phase.loc[
            (phase.index > end)
            & (phase.index <= end + pd.Timedelta(weeks=16))
        ] = "RECOVERY"

    cycle = pd.DataFrame(
        {"cycle_phase": phase},
        index=idx,
    )

    result = evaluate_historical_cycle(
        cycle_history=cycle,
        usrec_frame=_usrec(),
        start_year=1990,
    )

    summary = result["summary"]

    assert summary["episodes_evaluable"] == 4
    assert summary["slowdown_before_start_rate"] == pytest.approx(1.0)
    assert summary["contraction_near_start_rate"] == pytest.approx(1.0)
    assert summary["mean_contraction_overlap_share"] > 0.8


def test_usrec_is_validation_label_only():
    text = CONFIG.read_text(encoding="utf-8")
    assert '"usrec"' in text
    assert "validation label only" in text.lower()

    features = (
        ROOT / "src" / "macro" / "features.py"
    ).read_text(encoding="utf-8")
    assert '"usrec"' not in features


def test_engine_exposes_historical_validation():
    text = ENGINE.read_text(encoding="utf-8")

    assert "evaluate_historical_cycle" in text
    assert "historical_validation=historical_validation" in text


def test_page_shows_historical_validation_without_auto_calibration():
    text = PAGE.read_text(encoding="utf-8")

    for token in (
        "Historical Validation",
        "Slowdown vor Start",
        "Contraction nahe Start",
        "False Contraction",
        "RETROSPECTIVE_REVISED_DATA",
        "keine automatische Neukalibrierung",
    ):
        assert token.lower() in text.lower()


def test_v3241_uses_new_cache_to_force_longer_history_refresh():
    text = TOML.read_text(encoding="utf-8")
    assert "v3241_macro.sqlite3" in text


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(encoding="utf-8")
    assert "historical_validation" not in text
    assert "USREC" not in text


def test_python_files_parse():
    for path in (
        ROOT / "src" / "macro" / "historical_validation.py",
        ROOT / "src" / "macro" / "types.py",
        CONFIG,
        ENGINE,
        PAGE,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
