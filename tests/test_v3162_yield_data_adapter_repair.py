from pathlib import Path
import json

import pandas as pd
import pytest

from src.yield_spreads import (
    _parse_boc_2y,
    _parse_boe_curve_frame_2y,
    _parse_bundesbank_2y,
    _parse_japan_2y,
    _parse_rba_2y,
    _parse_rbnz_2y,
    _real_date_series,
    _validate_official_series,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "yield_spreads.py"
PAGE = ROOT / "pages" / "yield_spreads.py"


def test_real_date_parser_rejects_numeric_maturity_as_1970():
    values = pd.Series([2.0, 2.5, 3.0])
    dates = _real_date_series(values)
    assert dates.notna().sum() == 0


def test_bundesbank_series_specific_csv_parser():
    raw = (
        "meta;value\n"
        "TIME_PERIOD;OBS_VALUE\n"
        "2026-08-14;2.51\n"
        "2026-08-17;2.55\n"
        "2026-08-18;2.57\n"
    ).encode()
    series = _parse_bundesbank_2y(raw)
    assert series.index[-1] == pd.Timestamp("2026-08-18")
    assert series.iloc[-1] == pytest.approx(2.57)


def test_bank_of_canada_v39051_json_parser():
    payload = {
        "observations": [
            {"d": "2026-08-17", "V39051": {"v": "2.97"}},
            {"d": "2026-08-18", "V39051": {"v": "3.01"}},
        ]
    }
    series = _parse_boc_2y(json.dumps(payload).encode())
    assert series.iloc[-1] == pytest.approx(3.01)


def test_rba_parser_uses_exact_series_id():
    rows = [
        ["Title", "Australian Government 10 year bond", "Australian Government 2 year bond"],
        ["Series ID", "FCMYGBAG10D", "FCMYGBAG2D"],
        ["2026-08-14", "4.80", "4.40"],
        ["2026-08-17", "4.82", "4.43"],
        ["2026-08-18", "4.81", "4.41"],
    ]
    raw = "\n".join(",".join(row) for row in rows).encode()
    series = _parse_rba_2y(raw)
    assert series.index[-1] == pd.Timestamp("2026-08-18")
    assert series.iloc[-1] == pytest.approx(4.41)


def test_japan_parser_selects_2y_column():
    raw = (
        "Date,1Y,2Y,3Y\n"
        "2026-08-17,1.22,1.49,1.62\n"
        "2026-08-18,1.24,1.51,1.64\n"
    ).encode()
    series = _parse_japan_2y(raw)
    assert series.iloc[-1] == pytest.approx(1.51)


def test_boe_parser_uses_real_date_column_not_maturity():
    frame = pd.DataFrame(
        [
            ["Date", 0.5, 1.0, 2.0, 5.0],
            ["2026-08-14", 3.80, 3.70, 3.60, 3.90],
            ["2026-08-17", 3.82, 3.72, 3.62, 3.92],
            ["2026-08-18", 3.81, 3.71, 3.61, 3.91],
        ]
    )
    series = _parse_boe_curve_frame_2y(frame)
    assert series.index[-1] == pd.Timestamp("2026-08-18")
    assert series.iloc[-1] == pytest.approx(3.61)
    assert pd.Timestamp("1970-01-01") not in series.index


def test_rbnz_parser_finds_two_year_government_bond(monkeypatch):
    frame = pd.DataFrame(
        [
            ["", "", "Secondary market government bond closing yields (%pa)", "", ""],
            ["Date", "1 year", "2 year", "5 year", "10 year"],
            ["2026-08-14", 3.10, 3.21, 3.45, 3.70],
            ["2026-08-17", 3.12, 3.24, 3.47, 3.72],
            ["2026-08-18", 3.11, 3.23, 3.46, 3.71],
        ]
    )

    import src.yield_spreads as ys
    monkeypatch.setattr(ys, "_read_excel_candidates", lambda raw: [frame])

    series = _parse_rbnz_2y(b"dummy")
    assert series.iloc[-1] == pytest.approx(3.23)


def test_validation_rejects_1970_latest_date():
    series = pd.Series(
        [0.167],
        index=[pd.Timestamp("1970-01-01")],
        dtype=float,
    )
    with pytest.raises(ValueError, match="impossible latest date"):
        _validate_official_series(series, currency="GBP")


def test_validation_rejects_implausible_yield():
    today = pd.Timestamp.now().normalize()
    series = pd.Series([99.0], index=[today], dtype=float)
    with pytest.raises(ValueError, match="implausible 2Y yield"):
        _validate_official_series(series, currency="USD")


def test_v3162_replaces_fragile_fetchers():
    text = ENGINE.read_text(encoding="utf-8")
    for marker in (
        "fetch_eur_2y_v3162",
        "fetch_gbp_2y_v3162",
        "fetch_jpy_2y_v3162",
        "fetch_cad_2y_v3162",
        "fetch_aud_2y_v3162",
        "fetch_nzd_2y_v3162",
        "glcnominalddata.zip",
        "jgbcme.csv",
        "FCMYGBAG2D",
        "V39051",
    ):
        assert marker in text


def test_page_marks_adapter_repair_version():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.2 · REPAIRED OFFICIAL 2Y DATA ADAPTERS" in text
