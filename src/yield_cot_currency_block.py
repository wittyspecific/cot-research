from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from . import yield_cot_regime_event_study as _v3191_mod
from .yield_cot_conflict_oos import (
    _binomial_two_sided_v3192,
    _deoverlap_v3192,
    _oriented_returns_v3192,
    _wilson_v3192,
)


# V3.19.3 · CURRENCY-BLOCK ROBUSTNESS
#
# FINAL historical robustness test for the two frozen V3.19.2 conflict
# hypotheses. No threshold search, no ML, no parameter optimization.
#
# H1 stays frozen:
#   ACTIVE + STRONG/EXTREME 20D Rates CONFLICT
#   -> evaluate FX return in Rates direction after 8W
#
# H2 stays frozen:
#   EARLY + STRONG/EXTREME 20D Rates CONFLICT
#   -> evaluate FX return in Rates direction after 8W
#
# This module asks ONLY whether the already observed effect depends on a
# currency block, especially JPY.
#
# It does not calculate or modify COT states.

HYPOTHESES_V3193 = (
    {
        "hypothesis": "H1 · ACTIVE Conflict → Rates · 8W",
        "stage": "ACTIVE",
    },
    {
        "hypothesis": "H2 · EARLY Conflict → Rates · 8W",
        "stage": "EARLY",
    },
)

HORIZON_WEEKS_V3193 = 8
STRENGTHS_V3193 = frozenset({"STRONG", "EXTREME"})
RELATIONSHIP_V3193 = "CONFLICT"
DIRECTION_COL_V3193 = "rates20_raw_direction"
RETURN_COL_V3193 = "return_8w"


def _run_v3191_v3193(
    v3190_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Compatibility with both V3.19.1 public function names."""
    runner = getattr(
        _v3191_mod,
        "run_regime_aware_event_study_v3191",
        None,
    )
    if runner is None:
        runner = getattr(
            _v3191_mod,
            "run_regime_aware_event_study",
            None,
        )
    if runner is None:
        raise RuntimeError(
            "V3.19.3 findet keine V3.19.1 Event-Study-Funktion."
        )
    return runner(v3190_result)


def _normalize_schema_v3193(
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Compatibility adapter only. No COT state is calculated here."""
    if events is None or events.empty:
        return pd.DataFrame()

    out = events.copy()

    aliases = {
        "cot_stage": (
            "cot_stage",
            "cot_stage_v3191",
        ),
        "rates_strength": (
            "rates_strength",
            "rates_strength_v3191",
        ),
        "relationship": (
            "relationship",
            "relationship_v3191",
        ),
        "rates20_raw_direction": (
            "rates20_raw_direction",
            "rates20_raw_direction_v3191",
        ),
    }

    missing = []
    for canonical, candidates in aliases.items():
        if canonical in out.columns:
            continue
        source = next(
            (
                candidate
                for candidate in candidates
                if candidate in out.columns
            ),
            None,
        )
        if source is None:
            missing.append(canonical)
        else:
            out[canonical] = out[source]

    if missing:
        raise KeyError(
            "V3.19.3 Event-Schema inkompatibel. Fehlend: "
            + ", ".join(missing)
        )

    if "base" not in out.columns or "quote" not in out.columns:
        if "pair" not in out.columns:
            raise KeyError(
                "V3.19.3 benötigt base/quote oder pair."
            )
        pair = out["pair"].astype(str).str.upper().str.replace(
            r"[^A-Z]",
            "",
            regex=True,
        )
        if "base" not in out.columns:
            out["base"] = pair.str[:3]
        if "quote" not in out.columns:
            out["quote"] = pair.str[-3:]

    out["base"] = out["base"].astype(str).str.upper()
    out["quote"] = out["quote"].astype(str).str.upper()
    return out


def pair_contains_currency_v3193(
    row: Mapping[str, Any],
    currency: str,
) -> bool:
    ccy = str(currency).upper()
    return (
        str(row.get("base", "")).upper() == ccy
        or str(row.get("quote", "")).upper() == ccy
    )


def _frozen_events_v3193(
    all_events: pd.DataFrame,
    *,
    stage: str,
) -> pd.DataFrame:
    events = _normalize_schema_v3193(all_events)

    required = {
        "pair",
        "base",
        "quote",
        "available_date",
        "cot_stage",
        "rates_strength",
        "relationship",
        DIRECTION_COL_V3193,
        RETURN_COL_V3193,
    }
    missing = sorted(
        required.difference(events.columns)
    )
    if missing:
        raise KeyError(
            "V3.19.3 benötigt folgende Event-Felder: "
            + ", ".join(missing)
        )

    subset = events[
        events["cot_stage"].eq(stage)
        & events["rates_strength"].isin(
            STRENGTHS_V3193
        )
        & events["relationship"].eq(
            RELATIONSHIP_V3193
        )
    ].copy()

    subset = subset.dropna(
        subset=[
            "available_date",
            DIRECTION_COL_V3193,
            RETURN_COL_V3193,
        ]
    )

    # Same frozen V3.19.2 independence rule: no overlapping 8W
    # observations inside the same FX pair.
    return _deoverlap_v3192(
        subset,
        horizon_weeks=HORIZON_WEEKS_V3193,
    )


def _metric_v3193(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    oriented = _oriented_returns_v3192(
        frame,
        return_col=RETURN_COL_V3193,
        direction_col=DIRECTION_COL_V3193,
    )

    if oriented.empty:
        return {
            "n": 0,
            "Pairs": 0,
            "Hit Rate": np.nan,
            "Hit CI Low": np.nan,
            "Hit CI High": np.nan,
            "Binomial p": np.nan,
            "Median Return": np.nan,
            "Mean Return": np.nan,
            "Positive Pair Share": np.nan,
        }

    wins = int((oriented > 0).sum())
    n = int(len(oriented))
    low, high = _wilson_v3192(wins, n)

    pair_means = []
    for _, subset in frame.groupby("pair"):
        values = _oriented_returns_v3192(
            subset,
            return_col=RETURN_COL_V3193,
            direction_col=DIRECTION_COL_V3193,
        )
        if not values.empty:
            pair_means.append(float(values.mean()))

    positive_pair_share = (
        float(
            np.mean(
                np.asarray(pair_means) > 0
            )
        )
        if pair_means
        else np.nan
    )

    return {
        "n": n,
        "Pairs": int(frame["pair"].nunique()),
        "Hit Rate": float(wins / n),
        "Hit CI Low": low,
        "Hit CI High": high,
        "Binomial p": _binomial_two_sided_v3192(
            wins,
            n,
            0.5,
        ),
        "Median Return": float(oriented.median()),
        "Mean Return": float(oriented.mean()),
        "Positive Pair Share": positive_pair_share,
    }


def select_currency_block_v3193(
    frame: pd.DataFrame,
    *,
    currency: str,
    mode: str,
) -> pd.DataFrame:
    """Select ONLY or EXCLUDE a full currency leg block."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    ccy = str(currency).upper()
    mask = (
        frame["base"].astype(str).str.upper().eq(ccy)
        | frame["quote"].astype(str).str.upper().eq(ccy)
    )

    mode_value = str(mode).upper()
    if mode_value == "ONLY":
        return frame[mask].copy()
    if mode_value == "EXCLUDE":
        return frame[~mask].copy()

    raise ValueError(
        "mode must be ONLY or EXCLUDE"
    )


def _block_row_v3193(
    *,
    hypothesis: str,
    block: str,
    block_type: str,
    currency: str | None,
    subset: pd.DataFrame,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    metrics = _metric_v3193(subset)

    hit = float(metrics["Hit Rate"]) if np.isfinite(
        metrics["Hit Rate"]
    ) else np.nan
    mean_return = float(metrics["Mean Return"]) if np.isfinite(
        metrics["Mean Return"]
    ) else np.nan

    base_hit = float(baseline["Hit Rate"])
    base_mean = float(baseline["Mean Return"])

    return {
        "Hypothese": hypothesis,
        "Block": block,
        "Block Type": block_type,
        "Currency": currency or "",
        **metrics,
        "Δ Hit vs All": (
            hit - base_hit
            if np.isfinite(hit)
            and np.isfinite(base_hit)
            else np.nan
        ),
        "Δ Mean vs All": (
            mean_return - base_mean
            if np.isfinite(mean_return)
            and np.isfinite(base_mean)
            else np.nan
        ),
    }


def _robustness_read_v3193(
    rows: pd.DataFrame,
    *,
    hypothesis: str,
) -> dict[str, Any]:
    current = rows[
        rows["Hypothese"].eq(hypothesis)
    ].copy()

    if current.empty:
        return {
            "Hypothese": hypothesis,
            "Status": "INSUFFICIENT DATA",
        }

    baseline = current[
        current["Block"].eq("ALL")
    ]
    only_jpy = current[
        current["Block"].eq("ONLY JPY")
    ]
    ex_jpy = current[
        current["Block"].eq("EX JPY")
    ]
    loco = current[
        current["Block Type"].eq("LEAVE_ONE_OUT")
    ]

    if baseline.empty or ex_jpy.empty:
        return {
            "Hypothese": hypothesis,
            "Status": "INSUFFICIENT DATA",
        }

    base = baseline.iloc[0]
    ex = ex_jpy.iloc[0]

    ex_n = int(ex["n"])
    ex_hit = float(ex["Hit Rate"])
    ex_median = float(ex["Median Return"])
    ex_mean = float(ex["Mean Return"])
    ex_drop = float(ex["Δ Hit vs All"])

    loco_valid = loco[
        loco["n"].ge(20)
    ].copy()
    loco_survive = (
        (
            loco_valid["Hit Rate"].gt(0.50)
            & loco_valid["Mean Return"].gt(0)
            & loco_valid["Median Return"].gt(0)
        )
        if not loco_valid.empty
        else pd.Series(dtype=bool)
    )
    loco_share = (
        float(loco_survive.mean())
        if not loco_valid.empty
        else np.nan
    )

    only_jpy_hit = (
        float(only_jpy.iloc[0]["Hit Rate"])
        if not only_jpy.empty
        else np.nan
    )
    only_jpy_mean = (
        float(only_jpy.iloc[0]["Mean Return"])
        if not only_jpy.empty
        else np.nan
    )

    broad = (
        ex_n >= 30
        and np.isfinite(ex_hit)
        and ex_hit >= 0.55
        and np.isfinite(ex_median)
        and ex_median > 0
        and np.isfinite(ex_mean)
        and ex_mean > 0
        and np.isfinite(ex_drop)
        and ex_drop >= -0.05
        and np.isfinite(loco_share)
        and loco_share >= 0.70
    )

    jpy_dependent = (
        np.isfinite(only_jpy_hit)
        and only_jpy_hit >= 0.58
        and np.isfinite(only_jpy_mean)
        and only_jpy_mean > 0
        and (
            ex_n < 20
            or not np.isfinite(ex_hit)
            or ex_hit < 0.52
            or not np.isfinite(ex_mean)
            or ex_mean <= 0
        )
    )

    if broad:
        status = "BROAD CURRENCY ROBUSTNESS"
    elif jpy_dependent:
        status = "JPY-DEPENDENT"
    else:
        status = "MIXED / INCONCLUSIVE"

    worst_loco_hit = (
        float(loco_valid["Hit Rate"].min())
        if not loco_valid.empty
        else np.nan
    )
    worst_loco_mean = (
        float(loco_valid["Mean Return"].min())
        if not loco_valid.empty
        else np.nan
    )

    return {
        "Hypothese": hypothesis,
        "Status": status,
        "All n": int(base["n"]),
        "All Hit": float(base["Hit Rate"]),
        "ONLY JPY n": (
            int(only_jpy.iloc[0]["n"])
            if not only_jpy.empty
            else 0
        ),
        "ONLY JPY Hit": only_jpy_hit,
        "EX JPY n": ex_n,
        "EX JPY Hit": ex_hit,
        "EX JPY Mean": ex_mean,
        "EX JPY Δ Hit": ex_drop,
        "LOCO Survive Share": loco_share,
        "Worst LOCO Hit": worst_loco_hit,
        "Worst LOCO Mean": worst_loco_mean,
    }


def run_currency_block_robustness_v3193(
    v3190_result: Mapping[str, Any],
) -> dict[str, Any]:
    v3191 = _run_v3191_v3193(
        v3190_result
    )
    all_events = pd.DataFrame(
        v3191.get(
            "events",
            pd.DataFrame(),
        )
    )

    if all_events.empty:
        return {
            "summary": pd.DataFrame(),
            "blocks": pd.DataFrame(),
            "meta": {
                "note": "Keine V3.19.1 Events verfügbar.",
            },
        }

    all_events = _normalize_schema_v3193(
        all_events
    )

    available_currencies = sorted(
        set(
            all_events["base"]
            .dropna()
            .astype(str)
            .str.upper()
            .tolist()
        )
        | set(
            all_events["quote"]
            .dropna()
            .astype(str)
            .str.upper()
            .tolist()
        )
    )

    rows: list[dict[str, Any]] = []

    for spec in HYPOTHESES_V3193:
        hypothesis = str(spec["hypothesis"])
        events = _frozen_events_v3193(
            all_events,
            stage=str(spec["stage"]),
        )
        baseline = _metric_v3193(events)

        rows.append(
            _block_row_v3193(
                hypothesis=hypothesis,
                block="ALL",
                block_type="BASELINE",
                currency=None,
                subset=events,
                baseline=baseline,
            )
        )

        for block, mode in (
            ("ONLY JPY", "ONLY"),
            ("EX JPY", "EXCLUDE"),
        ):
            subset = select_currency_block_v3193(
                events,
                currency="JPY",
                mode=mode,
            )
            rows.append(
                _block_row_v3193(
                    hypothesis=hypothesis,
                    block=block,
                    block_type="JPY_CONTROL",
                    currency="JPY",
                    subset=subset,
                    baseline=baseline,
                )
            )

        for currency in available_currencies:
            subset = select_currency_block_v3193(
                events,
                currency=currency,
                mode="EXCLUDE",
            )
            rows.append(
                _block_row_v3193(
                    hypothesis=hypothesis,
                    block=f"EX {currency}",
                    block_type="LEAVE_ONE_OUT",
                    currency=currency,
                    subset=subset,
                    baseline=baseline,
                )
            )

    blocks = pd.DataFrame(rows)

    summary = pd.DataFrame(
        [
            _robustness_read_v3193(
                blocks,
                hypothesis=str(spec["hypothesis"]),
            )
            for spec in HYPOTHESES_V3193
        ]
    )

    return {
        "summary": summary,
        "blocks": blocks,
        "meta": {
            "currencies": available_currencies,
            "horizon": "8W",
            "hypotheses": 2,
            "method": (
                "Frozen H1/H2; same 8W pair de-overlap as V3.19.2; "
                "ONLY JPY, EX JPY and leave-one-currency-out."
            ),
            "interpretation": (
                "Historical robustness only. No new rule is selected here."
            ),
        },
    }


__all__ = [
    "run_currency_block_robustness_v3193",
    "select_currency_block_v3193",
    "pair_contains_currency_v3193",
]
