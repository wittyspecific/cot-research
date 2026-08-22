
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .atomic_models import build_atomic_models
from .breadth import evaluate_breadth
from .contraction_calibration import evaluate_contraction_candidates
from .composites import (
    add_equilibrium,
    build_family_indices,
    build_tier_indices,
    tier_snapshot,
)
from .config import SERIES_SPECS, load_config
from .cycle_core import (
    classify_cycle_history,
    phase_confidence,
    phase_divergence,
)
from .data_provider import FREDProvider
from .explain import build_drivers
from .features import (
    align_features_weekly,
    build_feature_library,
)
from .historical_validation import evaluate_historical_cycle
from .imminent_recession import evaluate_imminent_recession
from .liquidity import evaluate_liquidity
from .types import MacroNavigationResult


class MacroModelLibrary:
    """
    V3.24 public/reproducible macro navigation architecture.

    Important:
    - This is NOT Henrik Zeberg's proprietary model.
    - It implements public concepts: sequencing, hierarchy, phase-conditional
      imminent signals, and a separate liquidity modifier.
    - Exact proprietary weights/equilibrium construction are not copied.
    """

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        provider: FREDProvider | None = None,
    ):
        self.config = load_config(config_path)
        self.provider = provider or FREDProvider(self.config)

    def evaluate(
        self,
        *,
        as_of: str | pd.Timestamp | None = None,
        force_refresh: bool = False,
    ) -> MacroNavigationResult:
        series_map, status = self.provider.fetch_all(
            force_refresh=force_refresh
        )

        features = build_feature_library(
            series_map,
            self.config,
        )

        weekly_scores, weekly_raw = align_features_weekly(
            features,
            as_of=as_of,
        )

        family_frame = build_family_indices(
            weekly_scores,
            features,
        )
        tier_indices = build_tier_indices(
            family_frame,
            self.config,
        )
        cycle_frame = add_equilibrium(
            tier_indices,
            self.config,
        )
        cycle_history = classify_cycle_history(
            cycle_frame,
            self.config,
        )

        leading = tier_snapshot(
            cycle_history,
            family_frame,
            "leading",
        )
        coincident = tier_snapshot(
            cycle_history,
            family_frame,
            "coincident",
        )
        lagging = tier_snapshot(
            cycle_history,
            family_frame,
            "lagging",
        )

        cycle_phase = (
            str(cycle_history.iloc[-1]["cycle_phase"])
            if not cycle_history.empty
            else "UNCERTAIN"
        )

        divergence = phase_divergence(
            cycle_history
        )

        imminent = evaluate_imminent_recession(
            cycle_phase=cycle_phase,
            weekly_scores=weekly_scores,
            weekly_raw=weekly_raw,
            cycle_history=cycle_history,
            config=self.config,
        )

        if (
            cycle_phase == "SLOWDOWN"
            and imminent["state"] in {"BROAD", "IMMINENT"}
        ):
            transition_state = "LATE_SLOWDOWN"
        elif (
            cycle_phase == "EXPANSION"
            and leading.slope_13w is not None
            and leading.slope_13w < 0
            and leading.distance is not None
            and leading.distance < 10
        ):
            transition_state = "PEAK_WATCH"
        elif (
            cycle_phase == "CONTRACTION"
            and leading.slope_13w is not None
            and leading.slope_13w > 0
        ):
            transition_state = "RECOVERY_WATCH"
        else:
            transition_state = cycle_phase

        breadth = evaluate_breadth(
            weekly_scores,
            features,
            self.config,
        )

        liquidity = evaluate_liquidity(
            weekly_scores,
            features,
            self.config,
            cycle_phase=cycle_phase,
        )

        atomic = build_atomic_models(
            weekly_scores,
            weekly_raw,
            features,
            self.config,
        )

        historical_validation = evaluate_historical_cycle(
            cycle_history=cycle_history,
            usrec_frame=series_map.get("usrec"),
            start_year=1990,
        )

        contraction_calibration = evaluate_contraction_candidates(
            cycle_history=cycle_history,
            weekly_scores=weekly_scores,
            features=features,
            config=self.config,
            usrec_frame=series_map.get("usrec"),
            start_year=1990,
        )
        historical_validation[
            "contraction_calibration"
        ] = contraction_calibration

        required = [
            spec
            for spec in SERIES_SPECS
            if spec.required and spec.enabled
        ]
        ok_status = {"OK", "CACHE_FRESH", "CACHE_FALLBACK"}

        required_ok = sum(
            (
                spec.key in status
                and status[spec.key].status in ok_status
            )
            for spec in required
        )
        coverage = (
            required_ok / len(required)
            if required
            else 0.0
        )

        confidence = phase_confidence(
            cycle_history,
            data_coverage=coverage,
        )

        drivers = build_drivers(
            phase=cycle_phase,
            transition_state=transition_state,
            divergence=divergence,
            leading=leading,
            coincident=coincident,
            lagging=lagging,
            imminent=imminent,
            liquidity=liquidity,
        )

        as_of_value = (
            pd.Timestamp(cycle_history.index.max()).date().isoformat()
            if not cycle_history.empty
            else datetime.now(timezone.utc).date().isoformat()
        )

        family_votes = breadth.get(
            "family_votes",
            [],
        )

        history_cols = [
            c
            for c in (
                "leading",
                "leading_equilibrium",
                "leading_distance",
                "leading_slope_13w",
                "coincident",
                "coincident_equilibrium",
                "coincident_distance",
                "coincident_slope_13w",
                "lagging",
                "lagging_equilibrium",
                "lagging_distance",
                "lagging_slope_13w",
                "raw_phase",
                "cycle_phase",
            )
            if c in cycle_history.columns
        ]

        history_records = []
        if not cycle_history.empty:
            hist = cycle_history[history_cols].tail(520).copy()
            hist = hist.reset_index()
            for row in hist.to_dict("records"):
                record = {}
                for key, value in row.items():
                    if isinstance(value, pd.Timestamp):
                        record[key] = value.date().isoformat()
                    elif isinstance(value, (float, np.floating)):
                        record[key] = (
                            float(value)
                            if np.isfinite(value)
                            else None
                        )
                    else:
                        record[key] = value
                history_records.append(record)

        data_quality = {
            "required_series_ok": int(required_ok),
            "required_series_total": int(len(required)),
            "required_coverage": float(coverage),
            "series_status": {
                key: {
                    "series_id": item.series_id,
                    "status": item.status,
                    "rows": item.rows,
                    "cache_used": item.cache_used,
                    "note": item.note,
                }
                for key, item in status.items()
            },
            "point_in_time": {
                "mode": "CONSERVATIVE_RELEASE_LAG",
                "vintage_supported": False,
                "warning": (
                    "FRED graph CSV contains current/revised history. "
                    "Features are calculated in each series' native release frequency, "
                    "then aligned by conservative availability dates. "
                    "True historical-vintage backtests require ALFRED or another vintage source."
                ),
            },
            "architecture": {
                "regime_driver": "BUSINESS_CYCLE_CORE",
                "breadth_role": "DIAGNOSTIC_ONLY",
                "liquidity_role": "MODIFIER_ONLY",
                "market_structure_role": "SEPARATE_EXISTING_BOT_LAYER",
            },
        }

        return MacroNavigationResult(
            cycle_phase=cycle_phase,
            transition_state=transition_state,
            confidence=confidence,
            as_of=as_of_value,
            leading=leading,
            coincident=coincident,
            lagging=lagging,
            phase_divergence=divergence,
            imminent_recession=imminent,
            model_breadth=breadth,
            liquidity_modifier=liquidity,
            atomic_models=[x.to_dict() for x in atomic],
            family_consensus=family_votes,
            cycle_history=history_records,
            historical_validation=historical_validation,
            drivers=drivers,
            data_quality=data_quality,

            regime=cycle_phase,
            leading_cycle_score=leading.index,
            coincident_cycle_score=coincident.index,
            recession_transition_score=float(imminent.get("score", 0.0)),
            cross_asset_confirmation_score=None,
        )


def evaluate(
    *,
    config_path: str | Path | None = None,
    as_of: str | pd.Timestamp | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    return MacroModelLibrary(
        config_path=config_path
    ).evaluate(
        as_of=as_of,
        force_refresh=force_refresh,
    ).to_dict()
