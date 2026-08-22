
from pathlib import Path
import ast

import numpy as np
import pandas as pd
import pytest

from src.macro.config import load_config
from src.macro.cycle_core import raw_phase
from src.macro.normalization import robust_zscore_pit


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "ld,ls,cd,cs,expected",
    [
        (25, 5, 20, 3, "EXPANSION"),
        (-25, -8, 15, 1, "SLOWDOWN"),
        (-20, -5, -30, -8, "CONTRACTION"),
        (25, 8, -25, -2, "RECOVERY"),
    ],
)
def test_four_primary_cycle_phases(
    ld,
    ls,
    cd,
    cs,
    expected,
):
    assert raw_phase(
        ld,
        ls,
        cd,
        cs,
        5.0,
    ) == expected


def test_robust_normalization_is_prior_only():
    base = pd.Series(
        [1.0] * 30 + [100.0]
    )
    z = robust_zscore_pit(
        base,
        window=30,
        min_periods=10,
    )
    # Current extreme must not enter its own reference distribution.
    assert z.iloc[-1] > 10


def test_no_fifth_primary_late_slowdown_phase():
    source = (
        ROOT / "src" / "macro" / "cycle_core.py"
    ).read_text(encoding="utf-8")

    phases_section = source[
        source.index("PHASES ="):
        source.index("def raw_phase")
    ]
    assert "LATE_SLOWDOWN" not in phases_section


def test_macro_python_files_parse():
    for path in (ROOT / "src" / "macro").rglob("*.py"):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
