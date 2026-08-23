from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "test_v32901_research_panel_v1.py"


def test_v32931_target_test_parses():
    ast.parse(
        TARGET.read_text(encoding="utf-8"),
        filename=str(TARGET),
    )


def test_v32931_contract_tracks_restored_watchlist():
    source = TARGET.read_text(encoding="utf-8")

    assert '"Beobachtungsliste"' in source
    assert '"Seasonality Scanner"' in source
    assert "runpy.run_path(" in source
    assert 'run_name="__main__"' in source


def test_v32931_old_combined_tab_assertion_is_removed():
    source = TARGET.read_text(encoding="utf-8")

    old = (
        'assert \'"COT Scanner"\' in source '
        'and \'"Seasonality Scanner"\' in source'
    )

    assert old not in source
