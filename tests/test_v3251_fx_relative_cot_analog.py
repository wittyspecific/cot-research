from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.fx_relative_cot_analog import (
    FX_PAIRS,
    _merge_currency_legs,
    analyze_fx_relative_analogs,
    build_currency_leg,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ENGINE = ROOT / "src" / "fx_relative_cot_analog.py"
PAGE = ROOT / "pages" / "fx_relative_cot_analog.py"
OLD_ENGINE = ROOT / "src" / "cot_price_analog.py"
OLD_PAGE = ROOT / "pages" / "cot_price_analog.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _prices():
    idx = pd.date_range(
        "2010-01-01",
        "2026-08-21",
        freq="B",
        name="Date",
    )
    t = np.arange(
        len(idx),
        dtype=float,
    )
    close = (
        1.20
        + 0.00002 * t
        + 0.08 * np.sin(
            t / 90.0
        )
        + 0.03 * np.sin(
            t / 19.0
        )
    )
    return pd.DataFrame(
        {
            "close": close,
            "high": close * 1.003,
            "low": close * 0.997,
        },
        index=idx,
    )


def _cot(phase=0.0):
    dates = pd.date_range(
        "2010-01-05",
        "2026-08-18",
        freq="W-TUE",
    )
    t = np.arange(
        len(dates),
        dtype=float,
    )

    oi = (
        100_000.0
        + 2_000.0
        * np.sin(
            t / 15.0
            + phase
        )
    )

    asset_net = (
        20_000.0
        * np.sin(
            t / 18.0
            + phase
        )
    )
    lev_net = (
        -15_000.0
        * np.sin(
            t / 14.0
            + phase
        )
    )
    dealer_net = (
        -0.4
        * asset_net
    )
    nonrep_net = (
        4_000.0
        * np.sin(
            t / 9.0
            + phase
        )
    )

    def legs(net, base):
        return (
            base
            + np.maximum(
                net,
                0,
            ),
            base
            + np.maximum(
                -net,
                0,
            ),
        )

    dealer_long, dealer_short = legs(
        dealer_net,
        24_000.0,
    )
    am_long, am_short = legs(
        asset_net,
        30_000.0,
    )
    lf_long, lf_short = legs(
        lev_net,
        25_000.0,
    )
    nr_long, nr_short = legs(
        nonrep_net,
        10_000.0,
    )

    return pd.DataFrame(
        {
            "report_date": dates,
            "open_interest_all": oi,
            "dealer_long": dealer_long,
            "dealer_short": dealer_short,
            "asset_manager_long": am_long,
            "asset_manager_short": am_short,
            "leveraged_funds_long": lf_long,
            "leveraged_funds_short": lf_short,
            "nonreportable_long": nr_long,
            "nonreportable_short": nr_short,
        }
    )


def _research_items(text):
    tree = ast.parse(
        text,
        filename=str(APP),
    )

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Dict,
        ):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and key.value
                == "RESEARCH"
                and isinstance(
                    value,
                    ast.List,
                )
            ):
                lines = text.splitlines()
                return [
                    "\n".join(
                        lines[
                            item.lineno
                            - 1:
                            item.end_lineno
                        ]
                    )
                    for item in value.elts
                ]

    raise AssertionError(
        "RESEARCH navigation not found"
    )


def test_contains_exactly_28_fx_pairs_after_cad_extension():
    assert len(
        FX_PAIRS
    ) == 28

    expected = {
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "NZDUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "EURGBP",
        "EURJPY",
        "EURCHF",
        "EURAUD",
        "EURNZD",
        "EURCAD",
        "GBPJPY",
        "GBPCHF",
        "GBPAUD",
        "GBPNZD",
        "GBPCAD",
        "AUDJPY",
        "AUDCHF",
        "AUDNZD",
        "AUDCAD",
        "NZDJPY",
        "NZDCHF",
        "NZDCAD",
        "CADJPY",
        "CADCHF",
        "CHFJPY",
    }

    assert set(
        FX_PAIRS
    ) == expected



def test_usd_pair_orientation_is_correct():
    eur = build_currency_leg(
        _cot(
            phase=0.0
        ),
        "EUR",
    )
    jpy = build_currency_leg(
        _cot(
            phase=0.7
        ),
        "JPY",
    )

    eurusd = _merge_currency_legs(
        eur,
        None,
        base="EUR",
        quote="USD",
    )

    usdjpy = _merge_currency_legs(
        None,
        jpy,
        base="USD",
        quote="JPY",
    )

    assert np.allclose(
        eurusd[
            "relative_asset_manager_net_oi"
        ],
        eur[
            "asset_manager_net_oi"
        ],
        equal_nan=True,
    )

    assert np.allclose(
        usdjpy[
            "relative_asset_manager_net_oi"
        ],
        -jpy[
            "asset_manager_net_oi"
        ],
        equal_nan=True,
    )


def test_cross_is_base_minus_quote():
    eur = build_currency_leg(
        _cot(
            phase=0.0
        ),
        "EUR",
    )
    jpy = build_currency_leg(
        _cot(
            phase=0.7
        ),
        "JPY",
    )

    cross = _merge_currency_legs(
        eur,
        jpy,
        base="EUR",
        quote="JPY",
    )

    assert not cross.empty

    expected = (
        eur[
            "asset_manager_net_oi"
        ].reset_index(
            drop=True
        )
        - jpy[
            "asset_manager_net_oi"
        ].reset_index(
            drop=True
        )
    )

    assert np.allclose(
        cross[
            "relative_asset_manager_net_oi"
        ],
        expected,
        equal_nan=True,
    )


def test_fx_analog_returns_ranked_spaced_matches():
    result = analyze_fx_relative_analogs(
        _prices(),
        pair="EURJPY",
        base_cot=_cot(
            phase=0.0
        ),
        quote_cot=_cot(
            phase=0.7
        ),
        top_n=8,
        min_spacing_weeks=13,
        exclude_recent_weeks=26,
        outcome_horizon_weeks=8,
    )

    assert result[
        "available"
    ] is True

    matches = result[
        "matches"
    ]

    assert (
        matches["rank"].tolist()
        == list(
            range(
                1,
                len(
                    matches
                )
                + 1,
            )
        )
    )

    assert matches[
        "similarity"
    ].between(
        0,
        100,
    ).all()

    dates = sorted(
        pd.to_datetime(
            matches[
                "availability_date"
            ]
        ).tolist()
    )

    for left, right in zip(
        dates,
        dates[
            1:
        ],
    ):
        assert (
            right
            - left
        ).days >= 13 * 7


def test_simple_read_counts_bullish_and_bearish():
    result = analyze_fx_relative_analogs(
        _prices(),
        pair="GBPUSD",
        base_cot=_cot(
            phase=0.2
        ),
        quote_cot=None,
        top_n=8,
        outcome_horizon_weeks=8,
    )

    aggregate = result[
        "aggregate"
    ]

    assert (
        aggregate[
            "bullish_count"
        ]
        + aggregate[
            "bearish_count"
        ]
        + aggregate[
            "flat_count"
        ]
        == aggregate[
            "outcomes_available"
        ]
    )


def test_navigation_places_fx_page_after_existing_analog():
    text = APP.read_text(
        encoding="utf-8"
    )

    research = _research_items(
        text
    )

    macro = next(
        i
        for i, item in enumerate(
            research
        )
        if "pages/macro_model_library.py"
        in item
    )

    analog = next(
        i
        for i, item in enumerate(
            research
        )
        if "pages/cot_price_analog.py"
        in item
    )

    fx = next(
        i
        for i, item in enumerate(
            research
        )
        if "pages/fx_relative_cot_analog.py"
        in item
    )

    market = next(
        i
        for i, item in enumerate(
            research
        )
        if "pages/market_regime.py"
        in item
    )

    assert analog == macro + 1
    assert fx == analog + 1
    assert market == fx + 1


def test_existing_cot_price_analog_remains_independent():
    engine = OLD_ENGINE.read_text(
        encoding="utf-8"
    )
    page = OLD_PAGE.read_text(
        encoding="utf-8"
    )

    assert "fx_relative_cot_analog" not in engine
    assert "fx_relative_cot_analog" not in page
    assert "FX_PAIRS" not in engine
    assert "FX_PAIRS" not in page


def test_page_documents_usd_cross_and_cad_methodology():
    text = PAGE.read_text(
        encoding="utf-8"
    )

    for token in (
        "28 FX-Paare",
        "Base-COT minus Quote-COT",
        "DXY-COT",
        "6× bullish / 2× bearish",
        "keine kalibrierte Trade-Wahrscheinlichkeit",
        "CANADIAN DOLLAR",
    ):
        assert token.lower() in text.lower()



def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(
        encoding="utf-8"
    )

    assert (
        "fx_relative_cot_analog"
        not in text
    )


def test_files_parse():
    for path in (
        APP,
        ENGINE,
        PAGE,
        OLD_ENGINE,
        OLD_PAGE,
        WATCH,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(
                path
            ),
        )
