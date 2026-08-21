from pathlib import Path
import ast

from src.yield_cot_regime_event_study import (
    cot_phase_to_research_stage,
    rates_strength,
)

ROOT = Path(__file__).resolve().parents[1]
FX_ENGINE = ROOT / "src" / "yield_cot_fx_returns.py"
REGIME_ENGINE = ROOT / "src" / "yield_cot_regime_event_study.py"
PAGE = ROOT / "pages" / "yield_x_cot.py"


def test_phase_mapping_is_presentation_only():
    assert cot_phase_to_research_stage("EXTREME") == "WATCH"
    assert cot_phase_to_research_stage("TRANSITION") == "EARLY"
    assert cot_phase_to_research_stage("RELEASE") == "ACTIVE"
    assert cot_phase_to_research_stage("CONFIRMED") == "ACTIVE"


def test_rates_strength_bands():
    assert rates_strength(74.9) == "NORMAL"
    assert rates_strength(75) == "STRONG"
    assert rates_strength(89.9) == "STRONG"
    assert rates_strength(90) == "EXTREME"


def test_v3190_dataset_exposes_existing_currency_directions():
    text = FX_ENGINE.read_text(encoding="utf-8")
    assert '"base_cot_direction": int(base_dir)' in text
    assert '"quote_cot_direction": int(quote_dir)' in text


def test_regime_engine_does_not_redefine_cot_logic():
    text = REGIME_ENGINE.read_text(encoding="utf-8")
    for forbidden in (
        "NET_UPPER_PERCENTILE", "NET_LOWER_PERCENTILE", "NET_VALIDATION_WEEKS",
        "COMMERCIAL_RANGE_WEEKS", "hedger_cycle_state(", "latest_micro_trigger(", "macro_156w_state(",
    ):
        assert forbidden not in text


def test_page_states_cot_logic_unchanged():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.19.1 · REGIME-AWARE EVENT STUDY UI" in text
    assert "COT-Logik wird NICHT verändert" in text
    assert "EXTREME → WATCH" in text
    assert "TRANSITION → EARLY" in text


def test_files_parse():
    for path in (FX_ENGINE, REGIME_ENGINE, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
