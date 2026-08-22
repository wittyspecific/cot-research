from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.cot_price_analog import (
    _price_asof_reports,
    build_setup_frame,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "cot_price_analog.py"
PAGE = ROOT / "pages" / "cot_price_analog.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _named_price_index():
    idx = pd.date_range(
        "2024-01-01",
        periods=300,
        freq="B",
        name="Date",
    )
    close = np.linspace(
        100.0,
        130.0,
        len(idx),
    )
    return pd.DataFrame(
        {
            "close": close,
            "high": close * 1.01,
            "low": close * 0.99,
        },
        index=idx,
    )


def _cot():
    dates = pd.date_range(
        "2024-01-02",
        periods=45,
        freq="W-TUE",
    )
    t = np.arange(
        len(dates),
        dtype=float,
    )
    oi = np.full(
        len(dates),
        100_000.0,
    )

    return pd.DataFrame(
        {
            "report_date": dates,
            "open_interest_all": oi,
            "producer_long": 35_000 + 100 * t,
            "producer_short": 25_000 - 50 * t,
            "managed_money_long": 20_000 - 50 * t,
            "managed_money_short": 30_000 + 100 * t,
            "nonreportable_long": 12_000 + 20 * t,
            "nonreportable_short": 11_000 - 10 * t,
        }
    )


def test_price_asof_accepts_named_date_index():
    prices = _named_price_index()
    availability = pd.Series(
        pd.date_range(
            "2024-02-02",
            periods=10,
            freq="W-FRI",
        )
    )

    aligned = _price_asof_reports(
        prices,
        availability,
    )

    assert not aligned.empty
    assert "price_date" in aligned.columns
    assert "Date" not in aligned.columns
    assert (
        pd.to_datetime(
            aligned["price_date"]
        )
        <= pd.to_datetime(
            aligned["availability_date"]
        )
    ).all()


def test_build_setup_frame_works_with_named_date_index():
    setup = build_setup_frame(
        _named_price_index(),
        _cot(),
        "disaggregated",
    )

    assert setup["available"] is True
    assert not setup["frame"].empty
    assert "price_date" in setup["frame"].columns


def test_fix_is_scoped_to_price_alignment():
    source = ENGINE.read_text(
        encoding="utf-8"
    )

    assert 'index_column = right.columns[0]' in source
    assert 'index_column: "price_date"' in source
    assert "price_similarity" in source
    assert "cot_level_similarity" in source
    assert "cot_flow_similarity" in source


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(
        encoding="utf-8"
    )
    assert "cot_price_analog" not in text


def test_files_parse():
    for path in (
        ENGINE,
        PAGE,
        WATCH,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
