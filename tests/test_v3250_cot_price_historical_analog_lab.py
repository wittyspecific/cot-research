from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.cot_price_analog import (
    analyze_historical_analogs,
    build_setup_frame,
    forward_outcome,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "cot_price_analog.py"
ENGINE = ROOT / "src" / "cot_price_analog.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _prices():
    idx = pd.date_range(
        "2010-01-01",
        "2026-08-21",
        freq="B",
    )
    t = np.arange(
        len(idx),
        dtype=float,
    )
    close = (
        100.0
        + 0.015 * t
        + 8.0 * np.sin(
            t / 95.0
        )
        + 3.0 * np.sin(
            t / 21.0
        )
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
        "2010-01-05",
        "2026-08-18",
        freq="W-TUE",
    )
    t = np.arange(
        len(dates),
        dtype=float,
    )
    oi = 100_000.0 + 1000.0 * np.sin(t / 20.0)

    producer_net = (
        15_000.0 * np.sin(t / 17.0)
        + 5_000.0 * np.sin(t / 5.0)
    )
    managed_net = (
        -producer_net
        + 2_000.0 * np.sin(t / 9.0)
    )
    nonrep_net = (
        3_000.0 * np.sin(t / 11.0)
    )

    def legs(net, base):
        long = (
            base
            + np.maximum(net, 0)
        )
        short = (
            base
            + np.maximum(-net, 0)
        )
        return long, short

    producer_long, producer_short = legs(
        producer_net,
        30_000.0,
    )
    managed_long, managed_short = legs(
        managed_net,
        25_000.0,
    )
    nonrep_long, nonrep_short = legs(
        nonrep_net,
        12_000.0,
    )

    return pd.DataFrame(
        {
            "report_date": dates,
            "open_interest_all": oi,
            "producer_long": producer_long,
            "producer_short": producer_short,
            "managed_money_long": managed_long,
            "managed_money_short": managed_short,
            "nonreportable_long": nonrep_long,
            "nonreportable_short": nonrep_short,
        }
    )


def _research_items(text):
    tree = ast.parse(
        text,
        filename=str(APP),
    )
    for node in ast.walk(tree):
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
                and key.value == "RESEARCH"
                and isinstance(
                    value,
                    ast.List,
                )
            ):
                lines = text.splitlines()
                return [
                    "\n".join(
                        lines[
                            item.lineno - 1:
                            item.end_lineno
                        ]
                    )
                    for item in value.elts
                ]
    raise AssertionError(
        "RESEARCH navigation not found"
    )


def test_setup_uses_friday_like_availability_and_prior_price():
    setup = build_setup_frame(
        _prices(),
        _cot(),
        "disaggregated",
    )

    assert setup["available"] is True
    frame = setup["frame"]

    assert (
        pd.to_datetime(
            frame["availability_date"]
        )
        - pd.to_datetime(
            frame["report_date"]
        )
    ).dt.days.eq(3).all()

    assert (
        pd.to_datetime(
            frame["price_date"]
        )
        <= pd.to_datetime(
            frame["availability_date"]
        )
    ).all()


def test_setup_contains_price_and_cot_path_features():
    setup = build_setup_frame(
        _prices(),
        _cot(),
        "disaggregated",
    )
    frame = setup["frame"]

    for col in (
        "price_return_4w",
        "price_return_13w",
        "price_drawdown_26w",
        "producer_net_oi_percentile",
        "producer_net_oi_delta_1w",
        "producer_net_oi_delta_2w",
        "producer_net_oi_delta_4w",
        "managed_money_net_oi_delta_4w",
    ):
        assert col in frame.columns


def test_forward_outcome_uses_fixed_horizons_and_excursions():
    outcome = forward_outcome(
        _prices(),
        pd.Timestamp(
            "2018-09-14"
        ),
        excursion_horizon_weeks=8,
    )

    for key in (
        "return_2w",
        "return_4w",
        "return_8w",
        "return_12w",
        "mae",
        "mfe",
    ):
        assert key in outcome
        assert np.isfinite(
            float(
                outcome[key]
            )
        )


def test_analog_engine_returns_spaced_historical_matches():
    result = analyze_historical_analogs(
        _prices(),
        _cot(),
        "disaggregated",
        top_n=8,
        min_spacing_weeks=13,
        exclude_recent_weeks=26,
        excursion_horizon_weeks=8,
    )

    assert result["available"] is True
    matches = result["matches"]
    assert 1 <= len(matches) <= 8

    dates = sorted(
        pd.to_datetime(
            matches[
                "availability_date"
            ]
        ).tolist()
    )
    for left, right in zip(
        dates,
        dates[1:],
    ):
        assert (
            right - left
        ).days >= 13 * 7

    assert (
        matches["similarity"]
        .between(
            0.0,
            100.0,
        )
        .all()
    )


def test_navigation_places_macro_cot_then_analog_then_fx_between_macro_and_market():
    from pathlib import Path
    import ast
    app = Path(__file__).resolve().parents[1] / "app.py"
    text = app.read_text(encoding="utf-8")
    tree = ast.parse(text)
    research = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "RESEARCH" and isinstance(value, ast.List):
                research = value
    assert research is not None
    paths = []
    for item in research.elts:
        for child in ast.walk(item):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value.startswith("pages/"):
                paths.append(child.value); break
    assert paths == ["pages/opportunity_scanner.py", "pages/market_analysis_hub.py", "pages/currency_strength_hub.py", "pages/macro_regime.py"]



def test_page_documents_research_limits():
    text = PAGE.read_text(
        encoding="utf-8"
    )

    for token in (
        "COT × Price Historical Analog",
        "kein Entry-Signal",
        "50% Preisstruktur",
        "13 Wochen",
        "Futures-Roll-Risiko",
        "keine 80%-Gewinnwahrscheinlichkeit",
    ):
        assert token.lower() in text.lower()


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(
        encoding="utf-8"
    )

    assert "cot_price_analog" not in text
    assert "Historical Analog" not in text


def test_files_parse():
    for path in (
        APP,
        PAGE,
        ENGINE,
        WATCH,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
