from pathlib import Path
import ast

import numpy as np

from src.macro_cot_regime import (
    asset_specs,
    evaluate_cross_asset_positioning,
    load_config,
)
from src.rates_positioning import evaluate_rates_positioning


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "macro_cot_regime.toml"
ENGINE = ROOT / "src" / "macro_cot_regime.py"
RATES = ROOT / "src" / "rates_positioning.py"
PAGE = ROOT / "pages" / "macro_cot_regime.py"


def _state(key, label, score, direction="BULLISH", persistence=0.85, active_build=0.75):
    return {
        "key": key,
        "label": label,
        "available": True,
        "state": "VERY BULLISH" if score >= 55 else "BULLISH" if score >= 18 else "VERY BEARISH" if score <= -55 else "BEARISH" if score <= -18 else "NEUTRAL",
        "score": float(score),
        "persistence": float(persistence),
        "active_build_share": float(active_build),
        "direction_1w": direction,
        "direction_2w": direction,
        "direction_4w": direction,
        "position_strength": abs(float(score)),
    }


def _broad_bullish_rates():
    return {
        "treasury2y": _state("treasury2y", "US 2Y Treasury", 68),
        "treasury5y": _state("treasury5y", "US 5Y Treasury", 62),
        "treasury10y": _state("treasury10y", "US 10Y Treasury", 58),
        "treasury30y": _state("treasury30y", "US 30Y Treasury", 48),
    }


def test_rates_config_aggregates_four_tenors_once():
    config = load_config(CONFIG)
    weights = config["rates"]["contract_weights"]

    assert set(weights) == {
        "treasury2y",
        "treasury5y",
        "treasury10y",
        "treasury30y",
    }
    assert np.isclose(sum(weights.values()), 1.0)
    assert config["rates"]["basket_weight"] > 0

    specs = {spec.key: spec for spec in asset_specs(config)}
    for key in weights:
        assert specs[key].weight == 0.0
        assert specs[key].opportunity_group == "RATES_CURVE"


def test_broad_persistent_treasury_positioning_becomes_duration_accumulation():
    config = load_config(CONFIG)
    rates = evaluate_rates_positioning(
        _broad_bullish_rates(),
        config=config,
    )

    assert rates["available"] is True
    assert rates["state"] == "BROAD DURATION ACCUMULATION"
    assert rates["bullish_2w_breadth"] >= 0.99
    assert rates["bullish_4w_breadth"] >= 0.99
    assert rates["persistence"] >= 0.80
    assert rates["active_build_share"] >= 0.70
    assert rates["risk_off_confirmed"] is True


def test_single_tenor_bullish_does_not_create_broad_duration_accumulation():
    config = load_config(CONFIG)
    states = {
        "treasury2y": _state("treasury2y", "US 2Y Treasury", 70),
        "treasury5y": _state("treasury5y", "US 5Y Treasury", -35, direction="BEARISH"),
        "treasury10y": _state("treasury10y", "US 10Y Treasury", 0, direction="NEUTRAL", persistence=0.20, active_build=0.20),
        "treasury30y": _state("treasury30y", "US 30Y Treasury", 0, direction="NEUTRAL", persistence=0.20, active_build=0.20),
    }

    rates = evaluate_rates_positioning(states, config=config)
    assert rates["available"] is True
    assert rates["state"] != "BROAD DURATION ACCUMULATION"
    assert rates["bullish_4w_breadth"] < config["rates"]["breadth_strong"]


def test_cross_asset_breadth_counts_rates_basket_as_one_component():
    config = load_config(CONFIG)
    specs = asset_specs(config)
    states = _broad_bullish_rates()
    rates = evaluate_rates_positioning(states, config=config)

    cross = evaluate_cross_asset_positioning(
        states,
        specs,
        config=config,
        rates_state=rates,
    )

    assert cross["rates_included"] is True
    assert cross["risk_off_confirmations"] == 1
    assert cross["directional_assets"] == 1
    assert cross["risk_off_breadth"] == 1.0


def test_page_surfaces_compact_rates_positioning_block():
    text = PAGE.read_text(encoding="utf-8")
    for token in (
        "RATES POSITIONING",
        "TREASURY 2W BREADTH",
        "TREASURY 4W BREADTH",
        "ACTIVE DURATION BUILD",
        "Treasury Duration",
    ):
        assert token.lower() in text.lower()


def test_engine_wires_rates_into_alignment_pressure_opportunity_and_confirmation():
    text = ENGINE.read_text(encoding="utf-8")
    for token in (
        "evaluate_rates_positioning",
        "rates_state=rates_state",
        '"rates_positioning": rates_state',
        "Treasury Duration COT",
        "Treasury Duration",
    ):
        assert token in text


def test_python_files_parse():
    for path in (ENGINE, RATES, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
