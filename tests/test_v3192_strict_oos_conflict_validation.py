from pathlib import Path
import ast

import pandas as pd

from src.yield_cot_conflict_oos import (
    FREEZE_DATE_V3192,
    _binomial_two_sided_v3192,
    _deoverlap_v3192,
)


ROOT = Path(__file__).resolve().parents[1]
COT_CORE = [
    ROOT / "src" / "analysis.py",
    ROOT / "src" / "watchlist_macro_micro.py",
    ROOT / "src" / "micro_trigger.py",
    ROOT / "src" / "fx_relative.py",
]
ENGINE = ROOT / "src" / "yield_cot_conflict_oos.py"
PAGE = ROOT / "pages" / "yield_x_cot.py"


def test_frozen_hypothesis_date_is_explicit():
    assert str(FREEZE_DATE_V3192.date()) == "2026-08-21"


def test_deoverlap_removes_same_pair_events_inside_horizon():
    frame = pd.DataFrame(
        {
            "pair": ["EURUSD"] * 4,
            "available_date": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-15",
                    "2025-03-01",
                    "2025-05-01",
                ]
            ),
        }
    )
    out = _deoverlap_v3192(
        frame,
        horizon_weeks=8,
    )
    assert len(out) == 3
    assert pd.Timestamp("2025-01-15") not in set(
        out["available_date"]
    )


def test_exact_binomial_behaves_sensibly():
    assert _binomial_two_sided_v3192(50, 100) > 0.9
    assert _binomial_two_sided_v3192(70, 100) < 0.001


def test_hypotheses_are_hard_coded_not_searched():
    text = ENGINE.read_text(encoding="utf-8")
    assert "H1 · ACTIVE Conflict → Rates · 8W" in text
    assert "H2 · EARLY Conflict → Rates · 8W" in text
    assert "H3 · ACTIVE EXTREME Aligned → COT · 4W" in text
    assert "strength_values" in text
    assert "STRONG" in text
    assert "EXTREME" in text


def test_page_explains_retrospective_not_pristine_oos():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.19.2 · STRICT RETROSPECTIVE OOS CONFLICT VALIDATION UI" in text
    assert "Hypothesen-Freeze" in text
    assert "pristine" in text
    assert "COT-Core-Logik unverändert" in text


def test_v3192_does_not_patch_cot_core_files():
    for path in COT_CORE:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "V3.19.2" not in text


def test_engine_does_not_redefine_cot_logic():
    text = ENGINE.read_text(encoding="utf-8")
    for forbidden in (
        "NET_UPPER_PERCENTILE",
        "NET_LOWER_PERCENTILE",
        "NET_VALIDATION_WEEKS",
        "COMMERCIAL_RANGE_WEEKS",
        "hedger_cycle_state(",
        "latest_micro_trigger(",
        "macro_156w_state(",
    ):
        assert forbidden not in text


def test_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )



def test_runtime_schema_normalizer_v3192():
    from src.yield_cot_conflict_oos import (
        _normalize_v3191_event_schema_v3192,
    )

    import pandas as pd

    legacy = pd.DataFrame(
        {
            "cot_stage_v3191": ["ACTIVE"],
            "rates_strength_v3191": ["STRONG"],
            "relationship_v3191": ["CONFLICT"],
            "rates20_raw_direction_v3191": [-1],
        }
    )

    out = _normalize_v3191_event_schema_v3192(legacy)

    assert out.loc[0, "cot_stage"] == "ACTIVE"
    assert out.loc[0, "rates_strength"] == "STRONG"
    assert out.loc[0, "relationship"] == "CONFLICT"
    assert int(out.loc[0, "rates20_raw_direction"]) == -1
