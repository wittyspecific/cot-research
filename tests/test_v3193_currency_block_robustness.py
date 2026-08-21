from pathlib import Path
import ast

import pandas as pd

from src.yield_cot_currency_block import (
    HYPOTHESES_V3193,
    select_currency_block_v3193,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "yield_cot_currency_block.py"
PAGE = ROOT / "pages" / "yield_x_cot.py"

COT_CORE = [
    ROOT / "src" / "analysis.py",
    ROOT / "src" / "watchlist_macro_micro.py",
    ROOT / "src" / "micro_trigger.py",
    ROOT / "src" / "fx_relative.py",
]


def _sample():
    return pd.DataFrame(
        {
            "pair": [
                "USDJPY",
                "EURJPY",
                "EURUSD",
                "GBPUSD",
            ],
            "base": [
                "USD",
                "EUR",
                "EUR",
                "GBP",
            ],
            "quote": [
                "JPY",
                "JPY",
                "USD",
                "USD",
            ],
        }
    )


def test_h1_h2_are_frozen_and_h3_is_not_researched_again():
    names = [
        item["hypothesis"]
        for item in HYPOTHESES_V3193
    ]
    assert names == [
        "H1 · ACTIVE Conflict → Rates · 8W",
        "H2 · EARLY Conflict → Rates · 8W",
    ]


def test_only_jpy_block():
    out = select_currency_block_v3193(
        _sample(),
        currency="JPY",
        mode="ONLY",
    )
    assert set(out["pair"]) == {
        "USDJPY",
        "EURJPY",
    }


def test_ex_jpy_block():
    out = select_currency_block_v3193(
        _sample(),
        currency="JPY",
        mode="EXCLUDE",
    )
    assert set(out["pair"]) == {
        "EURUSD",
        "GBPUSD",
    }


def test_leave_usd_removes_every_pair_with_usd_leg():
    out = select_currency_block_v3193(
        _sample(),
        currency="USD",
        mode="EXCLUDE",
    )
    assert set(out["pair"]) == {
        "EURJPY",
    }


def test_no_cot_logic_is_defined_in_v3193():
    text = ENGINE.read_text(encoding="utf-8")
    for forbidden in (
        "NET_UPPER_PERCENTILE",
        "NET_LOWER_PERCENTILE",
        "NET_VALIDATION_WEEKS",
        "COMMERCIAL_RANGE_WEEKS",
        "hedger_cycle_state(",
        "latest_micro_trigger(",
        "macro_156w_state(",
    ):
        assert forbidden not in text


def test_page_contains_currency_block_research():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.19.3 · CURRENCY-BLOCK ROBUSTNESS UI" in text
    assert "ONLY JPY vs. EX JPY" in text
    assert "Leave-One-Currency-Out" in text
    assert "keine Parametersuche" in text


def test_cot_core_not_patched_by_v3193():
    for path in COT_CORE:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "V3.19.3" not in text


def test_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
