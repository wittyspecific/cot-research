from pathlib import Path
import ast
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
CORE = ROOT / "src" / "watchlist_macro_micro.py"


def _helper():
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_watchlist_setup_phase")
    ns = {"pd": pd}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(WATCH), "exec"), ns)
    return ns["_watchlist_setup_phase"]


def _decision(phase, macro_dir, micro_dir=0, fresh=False):
    return {"macro": {"phase": phase, "direction": macro_dir},
            "micro": {"direction": micro_dir, "fresh": fresh}}


def test_extreme_watch():
    assert _helper()(pd.Series({"macro_status_age_weeks": 4}), _decision("EXTREME", 1))["key"] == "EXTREME_WATCH"


def test_fresh_transition_same_micro_is_early_alignment():
    out = _helper()(pd.Series({"macro_status_age_weeks": 1}), _decision("TRANSITION", 1, 1, True))
    assert out["key"] == "EARLY_ALIGNMENT"


def test_transition_opposite_micro_is_conflict():
    out = _helper()(pd.Series({"macro_status_age_weeks": 1}), _decision("TRANSITION", 1, -1, True))
    assert out["key"] == "TIMING_CONFLICT"


def test_release_same_micro_is_structural_alignment():
    out = _helper()(pd.Series({"macro_status_age_weeks": 1}), _decision("RELEASE", -1, -1, True))
    assert out["key"] == "STRUCTURAL_ALIGNMENT"


def test_release_opposite_micro_is_pullback():
    out = _helper()(pd.Series({"macro_status_age_weeks": 1}), _decision("RELEASE", 1, -1, True))
    assert out["key"] == "MICRO_PULLBACK"


def test_renderer_has_phase_and_plan():
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_trader_table")
    body = ast.get_source_segment(text, fn) or ""
    assert "Phase / Plan" in body
    assert "_watchlist_setup_phase(row, decision)" in body
    assert 'decision.get("plan", "Warten")' in body


def test_decision_core_untouched_by_v3221():
    text = CORE.read_text(encoding="utf-8")
    assert "V3.22.1" not in text
    assert "_watchlist_setup_phase" not in text


def test_watchlist_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"), filename=str(WATCH))
