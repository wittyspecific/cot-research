from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.macro_cot_regime import (
    STATE_SEQUENCE,
    asset_specs,
    build_opportunity_map,
    classify_regime_transition,
    evaluate_combined_regime,
    evaluate_cot_positioning,
    evaluate_cross_asset_positioning,
    evaluate_macro_state,
    load_config,
)

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "macro_cot_regime.py"
ENGINE = ROOT / "src" / "macro_cot_regime.py"
CONFIG = ROOT / "config" / "macro_cot_regime.toml"
WATCH = ROOT / "pages" / "watchlist.py"


def _cot_fixture(*, structural="asset_manager", bullish=True, one_week_flip=False):
    dates = pd.date_range("2022-01-04", periods=180, freq="W-TUE")
    oi = np.full(len(dates), 100_000.0)
    net = np.linspace(-8_000, 14_000, len(dates)) if bullish else np.linspace(8_000, -14_000, len(dates))
    if one_week_flip and bullish:
        net[-5:] = [9_000, 10_000, 11_500, 14_000, 13_500]
    elif one_week_flip:
        net[-5:] = [-9_000, -10_000, -11_500, -14_000, -13_500]
    def legs(x, base):
        return base + np.maximum(x, 0.0), base + np.maximum(-x, 0.0)
    sl, ss = legs(net, 30_000.0)
    ml, ms = legs(-0.5 * net, 24_000.0)
    nl, ns = legs(0.2 * net, 12_000.0)
    frame = pd.DataFrame({"report_date": dates, "open_interest_all": oi, f"{structural}_long": sl, f"{structural}_short": ss, "nonreportable_long": nl, "nonreportable_short": ns})
    if structural == "asset_manager":
        frame["leveraged_funds_long"], frame["leveraged_funds_short"] = ml, ms
    else:
        frame["managed_money_long"], frame["managed_money_short"] = ml, ms
    return frame


def _macro_example():
    dates = pd.date_range("2025-01-03", periods=40, freq="W-FRI")
    ls = np.linspace(18.0, 16.0, len(dates))
    cs = np.linspace(10.0, 9.0, len(dates))
    ls[-5:] = [18.0, 14.0, 9.0, 5.0, 2.0]
    cs[-5:] = [10.0, 8.0, 6.0, 4.0, 3.0]
    return {
        "cycle_phase": "EXPANSION", "transition_state": "EXPANSION", "confidence": 0.82, "as_of": "2026-08-21",
        "leading": {"distance": 8.0, "slope_13w": float(ls[-1])}, "coincident": {"distance": 10.0, "slope_13w": float(cs[-1])},
        "cycle_history": [{"date": d.date().isoformat(), "leading_slope_13w": float(a), "coincident_slope_13w": float(b), "cycle_phase": "EXPANSION"} for d, a, b in zip(dates, ls, cs)],
        "model_breadth": {"tiers": {"leading": {"risk_off_breadth": 0.44, "risk_on_breadth": 0.20}}},
        "liquidity_modifier": {"state": "NEUTRAL", "channels": {"policy": 5.0, "credit": -5.0, "market": -30.0}},
    }


def _manual(key, label, score, persistence):
    state = "VERY BULLISH" if score >= 55 else "BULLISH" if score >= 18 else "VERY BEARISH" if score <= -55 else "BEARISH" if score <= -18 else "NEUTRAL"
    direction = "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"
    return {"key": key, "label": label, "available": True, "state": state, "score": float(score), "persistence": float(persistence), "position_strength": abs(float(score)), "direction_1w": direction, "direction_2w": direction, "direction_4w": direction}


def test_weights_are_central_and_4w_2w_dominate_1w():
    config = load_config(CONFIG)
    assert np.isclose(sum(config["transition_pressure"]["weights"].values()), 1.0)
    assert np.isclose(sum(config["cot"]["flow_weights"].values()), 1.0)
    assert config["transition_pressure"]["weights"]["cot_persistence"] == 0.30
    assert config["cot"]["flow_weights"]["4w"] > config["cot"]["flow_weights"]["2w"] > config["cot"]["flow_weights"]["1w"]


def test_cot_state_tracks_active_build_and_persistence():
    config = load_config(CONFIG)
    result = evaluate_cot_positioning(_cot_fixture(bullish=True), "tff", key="jpy", label="JPY", config=config)
    assert result["available"] is True
    assert result["direction_4w"] == "BULLISH"
    assert result["direction_2w"] == "BULLISH"
    assert result["persistence"] >= 0.85
    assert result["active_build_share"] is not None
    assert result["long_delta_4w"] is not None
    assert result["short_delta_4w"] is not None


def test_single_one_week_flip_cannot_overrule_2w_4w_structure():
    config = load_config(CONFIG)
    result = evaluate_cot_positioning(_cot_fixture(bullish=True, one_week_flip=True), "tff", key="jpy", label="JPY", config=config)
    assert result["direction_1w"] == "BEARISH"
    assert result["direction_4w"] == "BULLISH"
    assert result["persistence"] >= 0.50


def test_asset_specific_natural_gas_is_excluded_from_risk_breadth():
    config = load_config(CONFIG); specs = asset_specs(config)
    states = {"sp500": _manual("sp500", "S&P 500", -65, .85), "jpy": _manual("jpy", "JPY", 70, .85), "natural_gas": _manual("natural_gas", "Natural Gas", -90, 1.0)}
    result = evaluate_cross_asset_positioning(states, specs, config=config)
    assert result["risk_off_confirmations"] == 2
    ng = next(s for s in specs if s.key == "natural_gas")
    assert ng.weight == 0.0 and ng.risk_off_when == "ASSET_SPECIFIC"


def test_expansion_plus_defensive_cot_is_warning_not_contraction():
    config = load_config(CONFIG); macro = evaluate_macro_state(_macro_example(), config=config); specs = asset_specs(config)
    states = {
        "sp500": _manual("sp500", "S&P 500", -70, .90), "dow": _manual("dow", "Dow", -62, .85), "nasdaq": _manual("nasdaq", "Nasdaq", -35, .70),
        "jpy": _manual("jpy", "JPY", 72, .90), "chf": _manual("chf", "CHF", 65, .85), "treasury10y": _manual("treasury10y", "US 10Y", 28, .70),
        "gold": _manual("gold", "Gold", 0, .20), "copper": _manual("copper", "Copper", -20, .60), "crude": _manual("crude", "Crude", 0, .20), "cotton": _manual("cotton", "Cotton", -25, .65),
    }
    combined, cross = evaluate_combined_regime(macro, states, specs, config=config)
    assert macro["business_cycle_state"] in {"EXPANSION", "LATE EXPANSION"}
    assert combined["transition_code"] == "R3"
    assert 60.0 <= combined["transition_pressure"] <= 70.0
    assert "CONTRACTION" not in combined["transition_state"]
    assert combined["transition_pressure"] is not None
    assert cross["risk_off_breadth"] > cross["risk_on_breadth"]


def test_contraction_plus_risk_on_can_be_trough_watch():
    config = load_config(CONFIG)
    macro = {"business_cycle_state": "CONTRACTION", "macro_momentum_state": "IMPROVING", "leading_risk_off_breadth": .15, "leading_risk_on_breadth": .55, "financial_market_score": 25.0, "confidence": .80}
    cross = {"weighted_coverage": .85, "risk_off_breadth": .15, "risk_on_breadth": .68}
    state, code = classify_regime_transition(macro, cross, transition_pressure=72.0, config=config)
    assert code == "R7" and "TROUGH" in state


def test_opportunity_map_never_creates_buy_sell_entries():
    config = load_config(CONFIG); specs = asset_specs(config)
    macro = {"business_cycle_state": "LATE EXPANSION"}; combined = {"transition_code": "R3", "transition_pressure": 65.0, "target_transition_direction": "RISK_OFF"}; cross = {"risk_off_breadth": .70, "risk_on_breadth": .10}
    states = {s.key: _manual(s.key, s.label, -60 if s.risk_off_when == "BEARISH" else 60, .80) for s in specs if s.risk_off_when in {"BULLISH", "BEARISH"}}
    rows = build_opportunity_map(macro, combined, cross, states, specs, config=config)
    allowed = {"FAVOR", "WATCH", "NEUTRAL", "AVOID", "CONFLICT"}
    assert rows
    for row in rows:
        assert row["preference"] in allowed
        assert "BUY" not in str(row).upper()
        assert "SELL" not in str(row).upper()


def test_page_has_six_compact_v1_components_and_no_mock_fallback():
    text = PAGE.read_text(encoding="utf-8")
    for token in ("Macro × COT Regime", "Regime Transition Path", "Macro × COT Alignment Matrix", "Cross-Asset Positioning", "Trader Opportunity Map", "What Confirms the Transition?", "Why this regime?", "Macro Evidence", "COT Evidence", "Raw Diagnostics"):
        assert token.lower() in text.lower()
    assert "mock" not in text.lower()


def test_navigation_places_macro_cot_after_macro_before_analog():
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


def test_watchlist_uncoupled_and_state_machine_explicit():
    assert "macro_cot_regime" not in WATCH.read_text(encoding="utf-8")
    assert len(STATE_SEQUENCE) == 8 and STATE_SEQUENCE[0].startswith("R1") and STATE_SEQUENCE[-1].startswith("R8")


def test_files_parse():
    for path in (APP, PAGE, ENGINE): ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
