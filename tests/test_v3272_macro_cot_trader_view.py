from pathlib import Path
import ast

import pandas as pd

from src.cftc_market_resolver import resolve_universe_alias
from src.macro_cot_regime import (
    asset_specs,
    build_transition_confirmation,
    evaluate_cross_asset_positioning,
    load_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "macro_cot_regime.toml"
ENGINE = ROOT / "src" / "macro_cot_regime.py"
PAGE = ROOT / "pages" / "macro_cot_regime.py"
RESOLVER = ROOT / "src" / "cftc_market_resolver.py"


def _state(key, score, persistence):
    return {
        "key": key,
        "label": key,
        "available": True,
        "score": float(score),
        "persistence": float(persistence),
        "state": "BULLISH" if score > 0 else "BEARISH",
    }


def test_direct_universe_alias_resolves_all_standard_treasury_tenors():
    universe = pd.DataFrame(
        [
            {
                "market_and_exchange_names": "2-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",
                "cftc_contract_market_code": "042601",
            },
            {
                "market_and_exchange_names": "5-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",
                "cftc_contract_market_code": "044601",
            },
            {
                "market_and_exchange_names": "10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",
                "cftc_contract_market_code": "043602",
            },
            {
                "market_and_exchange_names": "U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE",
                "cftc_contract_market_code": "020601",
            },
        ]
    )

    cases = {
        "042601": ("2-YEAR U.S. TREASURY NOTES", "2-YEAR T-NOTE"),
        "044601": ("5-YEAR U.S. TREASURY NOTES", "5-YEAR T-NOTE"),
        "043602": ("10-YEAR U.S. TREASURY NOTES", "10-YEAR T-NOTE"),
        "020601": ("U.S. TREASURY BONDS", "30-YEAR TREASURY BOND"),
    }

    for expected_code, aliases in cases.items():
        resolved = resolve_universe_alias(universe, aliases)
        assert resolved is not None
        assert resolved["cftc_contract_market_code"] == expected_code
        assert resolved["resolved_via"] == "universe_alias"


def test_direction_specific_persistence_does_not_mix_risk_off_into_risk_on():
    config = load_config(CONFIG)
    specs = asset_specs(config)

    states = {
        # Equities bearish => Risk-Off, highly persistent.
        "sp500": _state("sp500", -70, 1.00),
        "dow": _state("dow", -60, 0.95),
        # JPY bullish => Risk-Off, highly persistent.
        "jpy": _state("jpy", 65, 0.90),
        # CHF bearish => Risk-On, but weak persistence.
        "chf": _state("chf", -45, 0.30),
    }

    cross = evaluate_cross_asset_positioning(
        states,
        specs,
        config=config,
        rates_state=None,
    )

    assert cross["persistence_score"] > 0.70
    assert cross["risk_off_persistence"] > 0.90
    assert cross["risk_on_persistence"] == 0.30


def test_transition_confirmation_uses_target_direction_persistence():
    config = load_config(CONFIG)

    macro = {
        "macro_momentum_state": "DETERIORATING",
        "leading_risk_on_breadth": 0.20,
        "financial_market_score": 20.0,
    }
    combined = {
        "target_transition_direction": "RISK_ON",
    }
    cross = {
        "persistence_score": 0.90,
        "risk_off_persistence": 0.95,
        "risk_on_persistence": 0.30,
        "risk_on_breadth": 0.15,
    }

    rows = build_transition_confirmation(
        macro,
        combined,
        cross,
        config=config,
        rates_state=None,
    )

    first = rows[0]
    assert "Risk-On" in first["trigger"]
    assert first["status"] == "WATCH"
    assert "30%" in first["why"]


def test_trader_page_is_slim_and_keeps_diagnostics_collapsed():
    text = PAGE.read_text(encoding="utf-8")

    for token in (
        "NEXT-REGIME PRESSURE",
        "Trader Read",
        "FOCUS MARKETS",
        "AVOID / CONFLICT",
        "Regime Transition Path",
        "Macro × COT Alignment Matrix",
        "Cross-Asset Positioning",
        "What Confirms the Transition?",
        "Details & Diagnostics",
        "Why this regime?",
        "Macro Evidence",
        "COT Evidence",
        "Raw Diagnostics",
        "RATES POSITIONING",
        "TREASURY 2W BREADTH",
        "TREASURY 4W BREADTH",
        "ACTIVE DURATION BUILD",
    ):
        assert token.lower() in text.lower()

    # The old permanently visible all-asset positioning table is gone.
    assert "position_frame" not in text
    assert 'section_line("4 · Trader Opportunity Map"' not in text
    assert text.count("st.expander(") == 1


def test_python_files_parse():
    for path in (ENGINE, PAGE, RESOLVER):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
