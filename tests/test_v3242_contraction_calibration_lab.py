from pathlib import Path
import ast

import pandas as pd

from src.macro.config import load_config
from src.macro.contraction_calibration import (
    build_candidate_series,
    evaluate_contraction_candidates,
)
from src.macro.features import FeatureFrame
from src.macro.types import FeatureSpec


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "macro" / "macro_model_library.py"
PAGE = ROOT / "pages" / "macro_model_library.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _feature(name, family):
    return FeatureFrame(
        FeatureSpec(
            name=name,
            tier="coincident",
            family=family,
            source_keys=("x",),
            description="test",
        ),
        pd.DataFrame(),
    )


def _fixture():
    idx = pd.date_range("1989-01-06", "2021-12-31", freq="W-FRI")
    cycle = pd.DataFrame(
        {
            "coincident_distance": 10.0,
            "coincident_slope_13w": 1.0,
            "cycle_phase": "EXPANSION",
        },
        index=idx,
    )
    scores = pd.DataFrame(
        {
            "Emp A": 40.0,
            "Emp B": 40.0,
            "Income A": 40.0,
            "Production A": 40.0,
            "Sales A": 40.0,
        },
        index=idx,
    )

    recessions = (
        ("1990-07-01", "1991-03-01"),
        ("2001-03-01", "2001-11-01"),
        ("2007-12-01", "2009-06-01"),
        ("2020-02-01", "2020-04-01"),
    )

    for start, end in recessions:
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        pre = (idx >= start - pd.Timedelta(weeks=20)) & (idx <= end)
        cycle.loc[pre, "coincident_distance"] = -25.0
        cycle.loc[pre, "coincident_slope_13w"] = -8.0
        for column in scores.columns:
            scores.loc[pre, column] = -60.0

    features = {
        "Emp A": _feature("Emp A", "employment"),
        "Emp B": _feature("Emp B", "employment"),
        "Income A": _feature("Income A", "income"),
        "Production A": _feature("Production A", "production"),
        "Sales A": _feature("Sales A", "sales"),
    }

    dates = pd.date_range("1989-01-01", "2021-12-01", freq="MS")
    values = pd.Series(0.0, index=dates)
    for start, end in recessions:
        values.loc[pd.Timestamp(start):pd.Timestamp(end)] = 1.0
    usrec = pd.DataFrame({"observation_date": dates, "value": values.values})
    return cycle, scores, features, usrec


def test_candidate_series_get_stricter():
    cfg = load_config(Path("/definitely/missing.toml"))
    cycle, scores, features, _ = _fixture()
    candidates, family = build_candidate_series(
        cycle_history=cycle,
        weekly_scores=scores,
        features=features,
        config=cfg,
    )
    assert not candidates.empty
    assert "risk_off_breadth" in family.columns
    assert candidates["A"].sum() <= candidates["CURRENT"].sum()
    assert candidates["B"].sum() <= candidates["A"].sum()
    assert candidates["C"].sum() <= candidates["B"].sum()


def test_calibration_separates_2020_shock_case():
    cfg = load_config(Path("/definitely/missing.toml"))
    cycle, scores, features, usrec = _fixture()
    result = evaluate_contraction_candidates(
        cycle_history=cycle,
        weekly_scores=scores,
        features=features,
        config=cfg,
        usrec_frame=usrec,
        start_year=1990,
    )
    assert result["mode"] == "RESEARCH_ONLY_NO_AUTO_CALIBRATION"
    assert "2020" in result["normal_cycle_definition"]
    assert any(row["shock_case"] for row in result["episodes"])


def test_engine_does_not_replace_cycle_phase_with_calibration():
    text = ENGINE.read_text(encoding="utf-8")
    phase_pos = text.index("cycle_phase =")
    calibration_call_pos = text.index("contraction_calibration = evaluate_contraction_candidates")
    assert phase_pos < calibration_call_pos
    assert "cycle_phase = contraction_calibration" not in text


def test_page_contains_calibration_lab():
    text = PAGE.read_text(encoding="utf-8")
    for token in (
        "Contraction Calibration Lab",
        "Candidate A",
        "Candidate B",
        "Candidate C",
        "Candidate D",
        "±13W Hit",
        "False Pos.",
        "2020",
        "keine automatische",
    ):
        assert token.lower() in text.lower()


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(encoding="utf-8")
    assert "contraction_calibration" not in text
    assert "Candidate D" not in text


def test_python_files_parse():
    for path in (
        ROOT / "src" / "macro" / "contraction_calibration.py",
        ENGINE,
        PAGE,
    ):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
