from __future__ import annotations

from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src import prices


ROOT = Path(__file__).resolve().parents[1]
PRICE_FILE = ROOT / "src" / "prices.py"


def _dates():
    return pd.date_range(
        "2026-01-02",
        periods=3,
        freq="D",
    )


def test_v33062_field_first_multiindex():
    frame = pd.DataFrame(
        np.array(
            [
                [1.10, 1.11],
                [1.20, 1.21],
                [1.30, 1.31],
            ]
        ),
        index=_dates(),
        columns=pd.MultiIndex.from_tuples(
            [
                ("Close", "EURUSD=X"),
                ("Open", "EURUSD=X"),
            ]
        ),
    )

    result = prices._extract_yfinance_close_series(
        frame,
        "EURUSD=X",
    )

    assert isinstance(result, pd.Series)
    assert result.tolist() == [1.10, 1.20, 1.30]


def test_v33062_ticker_first_multiindex():
    frame = pd.DataFrame(
        np.array(
            [
                [1.01, 1.10],
                [1.02, 1.20],
                [1.03, 1.30],
            ]
        ),
        index=_dates(),
        columns=pd.MultiIndex.from_tuples(
            [
                ("EURUSD=X", "Open"),
                ("EURUSD=X", "Close"),
            ]
        ),
    )

    result = prices._extract_yfinance_close_series(
        frame,
        "EURUSD=X",
    )

    assert isinstance(result, pd.Series)
    assert result.tolist() == [1.10, 1.20, 1.30]


def test_v33062_duplicate_flat_close_labels_still_return_series():
    frame = pd.DataFrame(
        np.array(
            [
                [10.0, 100.0, 9.0],
                [11.0, 101.0, 9.5],
                [12.0, 102.0, 10.0],
            ]
        ),
        index=_dates(),
        columns=[
            "Close",
            "Close",
            "Open",
        ],
    )

    result = prices._extract_yfinance_close_series(
        frame,
        "TEST",
    )

    assert isinstance(result, pd.Series)
    assert result.tolist() == [10.0, 11.0, 12.0]


def test_v33062_adj_close_remains_preferred():
    frame = pd.DataFrame(
        {
            "Close": [10.0, 11.0, 12.0],
            "Adj Close": [9.5, 10.5, 11.5],
        },
        index=_dates(),
    )

    result = prices._extract_yfinance_close_series(
        frame,
        "TEST",
    )

    assert result.tolist() == [9.5, 10.5, 11.5]


def test_v33062_existing_alignment_api_survives():
    source = PRICE_FILE.read_text(encoding="utf-8")

    assert "def align_prices_to_cot(" in source
    assert "def price_alignment_audit(" in source
    assert "price_date <= report_ts" in source
    assert "_same_iso_week(" in source


def test_v33062_prices_file_parses():
    ast.parse(
        PRICE_FILE.read_text(encoding="utf-8"),
        filename=str(PRICE_FILE),
    )
