from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.rates_cot_ml import (
    COMBINED_FEATURES_V3181,
    COT_STATE_FEATURES_V3181,
    RATES_ONLY_FEATURES_V3181,
    STRICT_LEAD_RELATIONS_V3181,
    _sequence_baseline_v3181,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "rates_cot_ml.py"
PAGE = ROOT / "pages" / "forex_matrix.py"


def test_feature_ablation_is_explicit():
    assert set(COT_STATE_FEATURES_V3181)
    assert set(RATES_ONLY_FEATURES_V3181)
    assert set(COT_STATE_FEATURES_V3181).issubset(
        set(COMBINED_FEATURES_V3181)
    )
    assert set(RATES_ONLY_FEATURES_V3181).issubset(
        set(COMBINED_FEATURES_V3181)
    )


def test_strict_lead_excludes_same_extreme():
    assert STRICT_LEAD_RELATIONS_V3181 == {
        "CONFLICT",
        "COT_NEUTRAL",
    }
    assert "SAME_EXTREME" not in STRICT_LEAD_RELATIONS_V3181


def test_sequence_baseline_uses_only_strict_lead():
    events = pd.DataFrame(
        [
            {
                "relation": "CONFLICT",
                "rates20_percentile": 95.0,
                "rates5_confirms": 1,
                "rates60_confirms": 1,
                "transition_6w": 1.0,
                "release_8w": 0.0,
            },
            {
                "relation": "COT_NEUTRAL",
                "rates20_percentile": 80.0,
                "rates5_confirms": 0,
                "rates60_confirms": 0,
                "transition_6w": 0.0,
                "release_8w": 0.0,
            },
            {
                "relation": "SAME_EXTREME",
                "rates20_percentile": 99.0,
                "rates5_confirms": 1,
                "rates60_confirms": 1,
                "transition_6w": 1.0,
                "release_8w": 1.0,
            },
        ]
    )

    table = _sequence_baseline_v3181(events)
    all_row = table[
        table["Sequenz"].eq("STRICT LEAD · alle")
    ].iloc[0]
    assert int(all_row["Episoden"]) == 2
    assert all_row["Transition ≤6W"] == 0.5


def test_page_contains_deep_dive_sections():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.18.1 · RATES COT ML DEEP DIVE" in text
    assert "Feature-Ablation" in text
    assert "Echter Rates-Lead" in text
    assert "Leave-One-Currency-Out" in text
    assert "STRICT LEAD" in text


def test_v3180_contract_is_preserved():
    text = ENGINE.read_text(encoding="utf-8")
    assert "V3.18.0 · RATES ↔ COT LEAD/LAG ML RESEARCH" in text
    assert "_run_rates_cot_ml_study_v3180 = run_rates_cot_ml_study" in text


def test_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
