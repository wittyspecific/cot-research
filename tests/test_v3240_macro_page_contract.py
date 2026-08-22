
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "macro_model_library.py"
WATCH = ROOT / "pages" / "watchlist.py"
CONFIG = ROOT / "config" / "macro_model_library.toml"


def test_page_implements_new_hierarchy():
    text = PAGE.read_text(
        encoding="utf-8"
    )

    for token in (
        "Business Cycle Core",
        "Imminent Recession Cluster",
        "Model Breadth & Makro ML Scatter",
        "Liquidity Modifier",
        "Leading → Coincident → Lagging",
        "definiert das Makro-Regime",
    ):
        assert token.lower() in text.lower()


def test_breadth_does_not_define_regime():
    text = (
        ROOT
        / "src"
        / "macro"
        / "macro_model_library.py"
    ).read_text(encoding="utf-8")

    phase_pos = text.index(
        "cycle_phase ="
    )
    breadth_pos = text.index(
        "breadth = evaluate_breadth("
    )

    assert phase_pos < breadth_pos


def test_watchlist_remains_uncoupled():
    text = WATCH.read_text(
        encoding="utf-8"
    )
    assert "src.macro" not in text
    assert "MacroModelLibrary" not in text


def test_config_has_no_single_master_macro_weight():
    text = CONFIG.read_text(
        encoding="utf-8"
    )

    assert "[tier_family_weights.leading]" in text
    assert "[tier_family_weights.coincident]" in text
    assert "[liquidity_weights]" in text
    assert "master_macro_score" not in text


def test_page_and_config_parse_contract():
    ast.parse(
        PAGE.read_text(encoding="utf-8"),
        filename=str(PAGE),
    )
