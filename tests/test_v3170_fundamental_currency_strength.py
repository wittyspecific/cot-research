from pathlib import Path
from types import SimpleNamespace
import ast

import pandas as pd

from src.fundamental_currency_strength import (
    build_fundamental_currency_strength,
)


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "forex_matrix.py"
FX = ROOT / "src" / "fx_relative.py"
ENGINE = ROOT / "src" / "fundamental_currency_strength.py"


def _universe():
    idx = pd.date_range("2026-01-01", periods=5, freq="B")
    return {
        c: SimpleNamespace(
            series=pd.Series([1, 1, 1, 1, 1], index=idx)
        )
        for c in ("EUR", "USD", "GBP", "JPY")
    }


def _snapshot_factory(eur_direction=1):
    def snapshot(pair, universe):
        base, quote = pair[:3], pair[3:6]
        if base == "EUR":
            sign = eur_direction
            pctl = 95.0
        elif quote == "EUR":
            sign = -eur_direction
            pctl = 95.0
        else:
            sign = 0
            pctl = 50.0

        return {
            "available": True,
            "delta_5d_bp": float(sign * 10),
            "percentile_5d": pctl,
            "delta_20d_bp": float(sign * 30),
            "percentile_20d": pctl,
            "delta_60d_bp": float(sign * 45),
            "percentile_60d": pctl,
        }
    return snapshot


def _profile(
    cycle_phase,
    extreme_direction,
    transition_state="HEDGE STABLE",
):
    return pd.DataFrame(
        [
            {
                "symbol": "EUR",
                "market_name": "Euro FX",
                "cycle_phase": cycle_phase,
                "extreme_direction": extreme_direction,
                "transition_state": transition_state,
                "regime_stage": (
                    2 if cycle_phase == "RELEASE" else 1
                ),
                "micro_trigger_direction": 1,
                "micro_trigger_age_weeks": 1,
                "micro_trigger_fresh": True,
            }
        ]
    )


def test_aligned_when_active_cot_and_rates_same_direction():
    out = build_fundamental_currency_strength(
        _profile("RELEASE", 1),
        _universe(),
        comparison_currencies=("EUR", "USD", "GBP", "JPY"),
        snapshot_fn=_snapshot_factory(1),
    )
    row = out.iloc[0]
    assert row["fundamental_state"] == "ALIGNED"
    assert row["bias_direction"] == 1
    assert "BULLISH" in row["rates_20d_label"]


def test_rates_lead_before_cot_release():
    out = build_fundamental_currency_strength(
        _profile("EXTREME", 1),
        _universe(),
        comparison_currencies=("EUR", "USD", "GBP", "JPY"),
        snapshot_fn=_snapshot_factory(1),
    )
    assert out.iloc[0]["fundamental_state"] == "RATES LEAD"


def test_conflict_when_cot_and_rates_disagree():
    out = build_fundamental_currency_strength(
        _profile("RELEASE", -1),
        _universe(),
        comparison_currencies=("EUR", "USD", "GBP", "JPY"),
        snapshot_fn=_snapshot_factory(1),
    )
    assert out.iloc[0]["fundamental_state"] == "CONFLICT"
    assert out.iloc[0]["bias_direction"] == 0


def test_page_contains_fundamental_strength_section():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.17.0 · FUNDAMENTAL CURRENCY STRENGTH" in text
    assert "Fundamentale Währungsstärke" in text
    assert "ALIGNED" in text
    assert "RATES LEAD" in text
    assert "COT LEADS" in text
    assert "CONFLICT" in text


def test_fx_profile_exposes_micro_and_cycle_dates():
    text = FX.read_text(encoding="utf-8")
    assert "latest_micro_trigger" in text
    assert '"micro_trigger_direction"' in text
    assert '"micro_trigger_age_weeks"' in text
    assert '"cot_release_date"' in text


def test_files_parse():
    for path in (PAGE, FX, ENGINE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
