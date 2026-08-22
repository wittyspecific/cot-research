from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.fx_relative_cot_analog import (
    FX_PAIRS,
    _merge_currency_legs,
    build_currency_leg,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "fx_relative_cot_analog.py"
PAGE = ROOT / "pages" / "fx_relative_cot_analog.py"
OLD_ENGINE = ROOT / "src" / "cot_price_analog.py"
OLD_PAGE = ROOT / "pages" / "cot_price_analog.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _cot(phase=0.0):
    dates = pd.date_range(
        "2018-01-02",
        periods=220,
        freq="W-TUE",
    )
    t = np.arange(len(dates), dtype=float)
    oi = np.full(len(dates), 100_000.0)

    am_net = 15_000.0 * np.sin(t / 18.0 + phase)
    lf_net = -10_000.0 * np.sin(t / 13.0 + phase)
    dealer_net = -0.3 * am_net
    nr_net = 3_000.0 * np.sin(t / 9.0 + phase)

    def legs(net, base):
        return (
            base + np.maximum(net, 0.0),
            base + np.maximum(-net, 0.0),
        )

    dealer_long, dealer_short = legs(dealer_net, 20_000.0)
    am_long, am_short = legs(am_net, 30_000.0)
    lf_long, lf_short = legs(lf_net, 25_000.0)
    nr_long, nr_short = legs(nr_net, 10_000.0)

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


def test_fx_universe_has_28_pairs_after_adding_cad():
    assert len(FX_PAIRS) == 28

    for pair in (
        "USDCAD",
        "EURCAD",
        "GBPCAD",
        "AUDCAD",
        "NZDCAD",
        "CADJPY",
        "CADCHF",
    ):
        assert pair in FX_PAIRS


def test_usdcad_inverts_cad_leg():
    cad = build_currency_leg(
        _cot(phase=0.4),
        "CAD",
    )

    usdcad = _merge_currency_legs(
        None,
        cad,
        base="USD",
        quote="CAD",
    )

    assert np.allclose(
        usdcad["relative_asset_manager_net_oi"],
        -cad["asset_manager_net_oi"],
        equal_nan=True,
    )


def test_eurcad_is_eur_minus_cad():
    eur = build_currency_leg(
        _cot(phase=0.0),
        "EUR",
    )
    cad = build_currency_leg(
        _cot(phase=0.4),
        "CAD",
    )

    eurcad = _merge_currency_legs(
        eur,
        cad,
        base="EUR",
        quote="CAD",
    )

    expected = (
        eur["asset_manager_net_oi"].reset_index(drop=True)
        - cad["asset_manager_net_oi"].reset_index(drop=True)
    )

    assert np.allclose(
        eurcad["relative_asset_manager_net_oi"],
        expected,
        equal_nan=True,
    )


def test_cadjpy_is_cad_minus_jpy():
    cad = build_currency_leg(
        _cot(phase=0.4),
        "CAD",
    )
    jpy = build_currency_leg(
        _cot(phase=0.8),
        "JPY",
    )

    cadjpy = _merge_currency_legs(
        cad,
        jpy,
        base="CAD",
        quote="JPY",
    )

    expected = (
        cad["leveraged_funds_net_oi"].reset_index(drop=True)
        - jpy["leveraged_funds_net_oi"].reset_index(drop=True)
    )

    assert np.allclose(
        cadjpy["relative_leveraged_funds_net_oi"],
        expected,
        equal_nan=True,
    )


def test_page_includes_canadian_dollar_and_28_pairs():
    text = PAGE.read_text(encoding="utf-8")

    assert '"CAD": ("CANADIAN DOLLAR", "CANADIAN")' in text
    assert "28 FX-Paare" in text
    assert "EUR, GBP, AUD, NZD, JPY, CHF, CAD und USD" in text


def test_existing_cot_price_analog_is_still_independent():
    engine = OLD_ENGINE.read_text(encoding="utf-8")
    page = OLD_PAGE.read_text(encoding="utf-8")

    assert "FX_PAIRS" not in engine
    assert "CADJPY" not in engine
    assert "CADJPY" not in page


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(encoding="utf-8")
    assert "fx_relative_cot_analog" not in text


def test_files_parse():
    for path in (
        ENGINE,
        PAGE,
        OLD_ENGINE,
        OLD_PAGE,
        WATCH,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
