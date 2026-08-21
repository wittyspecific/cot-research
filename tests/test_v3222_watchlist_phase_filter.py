from pathlib import Path
import ast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
CORE = ROOT / "src" / "watchlist_macro_micro.py"
MICRO = ROOT / "src" / "micro_trigger.py"


def _load_helpers():
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)

    wanted = {
        "_watchlist_setup_phase",
        "_watchlist_phase_filter_groups",
        "_watchlist_phase_filter_match",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in wanted
    ]

    names = {node.name for node in nodes}
    assert names == wanted

    namespace = {
        "pd": pd,
        "classify_macro_micro_trade": lambda row: {},
    }
    exec(
        compile(
            ast.Module(body=nodes, type_ignores=[]),
            str(WATCH),
            "exec",
        ),
        namespace,
    )
    return namespace


def _decision(phase, macro_dir, micro_dir=0, fresh=False):
    return {
        "macro": {
            "phase": phase,
            "direction": macro_dir,
        },
        "micro": {
            "direction": micro_dir,
            "fresh": fresh,
        },
    }


def test_early_alignment_belongs_to_early_and_alignment():
    ns = _load_helpers()
    row = pd.Series({"macro_status_age_weeks": 1})
    decision = _decision("TRANSITION", 1, 1, True)

    groups = ns["_watchlist_phase_filter_groups"](
        row,
        decision,
    )

    assert "EARLY ALIGNMENT" in groups
    assert "ALIGNMENT" in groups
    assert "TRANSITION" in groups


def test_release_pullback_belongs_to_pullback_and_conflict():
    ns = _load_helpers()
    row = pd.Series({"macro_status_age_weeks": 1})
    decision = _decision("RELEASE", 1, -1, True)

    groups = ns["_watchlist_phase_filter_groups"](
        row,
        decision,
    )

    assert "PULLBACK" in groups
    assert "CONFLICT" in groups


def test_confirmed_alignment_belongs_to_confirmed_and_alignment():
    ns = _load_helpers()
    row = pd.Series({"macro_status_age_weeks": 2})
    decision = _decision("CONFIRMED", -1, -1, True)

    groups = ns["_watchlist_phase_filter_groups"](
        row,
        decision,
    )

    assert "CONFIRMED" in groups
    assert "ALIGNMENT" in groups


def test_watchlist_has_phase_multiselect_and_applies_it():
    text = WATCH.read_text(encoding="utf-8")

    assert 'st.multiselect(' in text
    assert '"Setup-Phase"' in text

    for option in (
        "EARLY ALIGNMENT",
        "ALIGNMENT",
        "PULLBACK",
        "CONFIRMED",
        "TRANSITION",
        "WATCH",
        "CONFLICT",
    ):
        assert f'"{option}"' in text

    assert "_watchlist_phase_filter_match(" in text
    assert "phase_filter" in text
    assert "filtered = filtered.loc[_phase_mask].copy()" in text


def test_existing_v3221_phase_renderer_survives():
    text = WATCH.read_text(encoding="utf-8")

    assert '"Phase / Plan"' in text
    assert '"EARLY ALIGNMENT"' in text
    assert '"MICRO PULLBACK"' in text
    assert '"CONFIRMED ALIGNMENT"' in text


def test_decision_core_and_micro_core_untouched():
    for path in (CORE, MICRO):
        text = path.read_text(encoding="utf-8")
        assert "V3.22.2" not in text
        assert "_watchlist_phase_filter_groups" not in text


def test_watchlist_parses():
    ast.parse(
        WATCH.read_text(encoding="utf-8"),
        filename=str(WATCH),
    )
