
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .config import MacroConfig, SERIES_SPECS
from .normalization import (
    direct_centered_score,
    robust_zscore_pit,
    z_to_score,
)
from .types import FeatureSpec


@dataclass
class FeatureFrame:
    spec: FeatureSpec
    frame: pd.DataFrame

    def current_raw(self):
        clean = self.frame.dropna(subset=["raw"])
        return float(clean.iloc[-1]["raw"]) if not clean.empty else None


def _spec_map():
    return {spec.key: spec for spec in SERIES_SPECS}


def _native_base(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(
            columns=["observation_date", "availability_date", "value"]
        )

    work = frame[
        ["observation_date", "availability_date", "value"]
    ].copy()
    work["observation_date"] = pd.to_datetime(
        work["observation_date"], errors="coerce"
    )
    work["availability_date"] = pd.to_datetime(
        work["availability_date"], errors="coerce"
    )
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work.dropna().sort_values("observation_date")

    if frequency == "daily":
        # Daily financial series are reduced to one observation per week before
        # any transformation. This avoids treating 5 business days as 5
        # independent macro releases.
        work["_period"] = work["observation_date"].dt.to_period("W-FRI")
        work = (
            work.groupby("_period", as_index=False)
            .tail(1)
            .drop(columns=["_period"])
        )

    return work.reset_index(drop=True)


def _window_for_frequency(config: MacroConfig, frequency: str) -> tuple[int, int]:
    cfg = config.section("normalization")
    years = int(cfg.get("years", 10))

    if frequency == "monthly":
        return (
            max(36, 12 * years),
            int(cfg.get("monthly_min_obs", 36)),
        )
    return (
        max(104, 52 * years),
        int(cfg.get("weekly_min_obs", 104)),
    )


def _feature(
    *,
    name: str,
    tier: str,
    family: str,
    source_keys: tuple[str, ...],
    description: str,
    raw_frame: pd.DataFrame,
    raw_series: pd.Series,
    config: MacroConfig,
    frequency: str,
    orientation: float = 1.0,
    direct: tuple[float, float] | None = None,
) -> FeatureFrame:
    out = raw_frame[
        ["observation_date", "availability_date"]
    ].copy()

    raw = pd.to_numeric(raw_series, errors="coerce").reset_index(drop=True)
    out["raw"] = raw

    if direct is not None:
        center, scale = direct
        out["score"] = direct_centered_score(
            raw,
            center=center,
            scale=scale,
            orientation=orientation,
        )
    else:
        window, min_obs = _window_for_frequency(config, frequency)
        z = robust_zscore_pit(
            raw,
            window=window,
            min_periods=min_obs,
        )
        out["score"] = z_to_score(
            z * float(orientation),
            clip=float(config.section("normalization").get("z_clip", 3.5)),
        )

    return FeatureFrame(
        FeatureSpec(
            name=name,
            tier=tier,
            family=family,
            source_keys=source_keys,
            description=description,
        ),
        out,
    )


def _single(
    series_map,
    key: str,
    config: MacroConfig,
    *,
    name: str,
    tier: str,
    family: str,
    transform: Callable[[pd.Series], pd.Series],
    description: str,
    orientation: float = 1.0,
    direct: tuple[float, float] | None = None,
) -> FeatureFrame | None:
    specs = _spec_map()
    frame = _native_base(
        series_map.get(key),
        specs[key].frequency,
    )
    if frame.empty:
        return None

    raw = transform(frame["value"].astype(float))
    return _feature(
        name=name,
        tier=tier,
        family=family,
        source_keys=(key,),
        description=description,
        raw_frame=frame,
        raw_series=raw,
        config=config,
        frequency=specs[key].frequency,
        orientation=orientation,
        direct=direct,
    )


def _rate_spread(
    series_map,
    left_key: str,
    right_key: str,
    config: MacroConfig,
    *,
    name: str,
    tier: str,
    family: str,
    description: str,
    direct: tuple[float, float],
) -> FeatureFrame | None:
    specs = _spec_map()
    left = _native_base(series_map.get(left_key), specs[left_key].frequency)
    right = _native_base(series_map.get(right_key), specs[right_key].frequency)

    if left.empty or right.empty:
        return None

    left = left.rename(
        columns={
            "observation_date": "left_date",
            "availability_date": "left_avail",
            "value": "left_value",
        }
    ).sort_values("left_date")
    right = right.rename(
        columns={
            "observation_date": "right_date",
            "availability_date": "right_avail",
            "value": "right_value",
        }
    ).sort_values("right_date")

    merged = pd.merge_asof(
        left,
        right,
        left_on="left_date",
        right_on="right_date",
        direction="backward",
    ).dropna(subset=["left_value", "right_value"])

    if merged.empty:
        return None

    base = pd.DataFrame(
        {
            "observation_date": merged["left_date"],
            "availability_date": pd.concat(
                [merged["left_avail"], merged["right_avail"]],
                axis=1,
            ).max(axis=1),
        }
    )
    raw = merged["left_value"] - merged["right_value"]

    return _feature(
        name=name,
        tier=tier,
        family=family,
        source_keys=(left_key, right_key),
        description=description,
        raw_frame=base,
        raw_series=raw,
        config=config,
        frequency="weekly",
        direct=direct,
    )


def _pct(periods: int):
    return lambda s: s.pct_change(periods, fill_method=None)


def _diff(periods: int):
    return lambda s: s.diff(periods)


def _level(s):
    return s


def _rolling_mean_diff(diff_periods: int, mean_periods: int):
    def _inner(s):
        return s.diff(diff_periods).rolling(
            mean_periods,
            min_periods=mean_periods,
        ).mean()
    return _inner


def build_feature_library(
    series_map: dict[str, pd.DataFrame],
    config: MacroConfig,
) -> dict[str, FeatureFrame]:
    features: list[FeatureFrame | None] = []

    # ----------------------------
    # LEADING
    # ----------------------------
    for key, label in (
        ("building_permits", "Building Permits"),
        ("housing_starts", "Housing Starts"),
    ):
        features.extend(
            [
                _single(
                    series_map, key, config,
                    name=f"{label} YoY",
                    tier="leading",
                    family="housing",
                    transform=_pct(12),
                    description=f"{label}: Veränderung gegenüber Vorjahr.",
                ),
                _single(
                    series_map, key, config,
                    name=f"{label} 3M",
                    tier="leading",
                    family="housing",
                    transform=_pct(3),
                    description=f"{label}: 3-Monats-Momentum in nativer Monatsfrequenz.",
                ),
            ]
        )

    features.extend(
        [
            _single(
                series_map, "manufacturing_orders", config,
                name="Manufacturing Orders YoY",
                tier="leading",
                family="orders",
                transform=_pct(12),
                description="Öffentlicher New-Orders-Proxy gegenüber Vorjahr.",
            ),
            _single(
                series_map, "manufacturing_orders", config,
                name="Manufacturing Orders 3M",
                tier="leading",
                family="orders",
                transform=_pct(3),
                description="Öffentlicher New-Orders-Proxy über 3 Monate.",
            ),
            _single(
                series_map, "initial_claims", config,
                name="Initial Claims 4W",
                tier="leading",
                family="labor_leading",
                transform=_pct(4),
                description="Steigende Initial Claims sind ein frühes Arbeitsmarkt-Warnsignal.",
                orientation=-1.0,
            ),
            _single(
                series_map, "initial_claims", config,
                name="Initial Claims 13W",
                tier="leading",
                family="labor_leading",
                transform=_pct(13),
                description="Breitere Claims-Deterioration über ca. 13 Wochen.",
                orientation=-1.0,
            ),
            _rate_spread(
                series_map,
                "us10y",
                "us2y",
                config,
                name="10Y-2Y Yield Spread",
                tier="leading",
                family="yield_curve",
                description="Yield-curve slope; inversion is negative.",
                direct=(0.0, 1.0),
            ),
            _rate_spread(
                series_map,
                "us10y",
                "us3m",
                config,
                name="10Y-3M Yield Spread",
                tier="leading",
                family="yield_curve",
                description="Yield-curve slope; inversion is negative.",
                direct=(0.0, 1.0),
            ),
            _single(
                series_map, "consumer_sentiment", config,
                name="Consumer Sentiment 3M",
                tier="leading",
                family="sentiment",
                transform=_diff(3),
                description="Forward-looking sentiment momentum over 3 months.",
            ),
            _single(
                series_map, "consumer_sentiment", config,
                name="Consumer Sentiment 6M",
                tier="leading",
                family="sentiment",
                transform=_diff(6),
                description="Forward-looking sentiment momentum over 6 months.",
            ),
        ]
    )

    # ----------------------------
    # COINCIDENT
    # ----------------------------
    features.extend(
        [
            _single(
                series_map, "payems", config,
                name="Payroll Monthly Change",
                tier="coincident",
                family="employment",
                transform=_diff(1),
                description="Month-on-month payroll change in native monthly frequency.",
            ),
            _single(
                series_map, "payems", config,
                name="Payroll 3M Average Change",
                tier="coincident",
                family="employment",
                transform=_rolling_mean_diff(1, 3),
                description="3-month average payroll change; no weekly diff proxy.",
            ),
            _single(
                series_map, "unemployment", config,
                name="Unemployment 3M Change",
                tier="coincident",
                family="employment",
                transform=_diff(3),
                description="Rising unemployment weakens coincident employment.",
                orientation=-1.0,
            ),
            _single(
                series_map, "industrial_production", config,
                name="Industrial Production YoY",
                tier="coincident",
                family="production",
                transform=_pct(12),
                description="Industrial production growth versus year ago.",
            ),
            _single(
                series_map, "industrial_production", config,
                name="Industrial Production 3M",
                tier="coincident",
                family="production",
                transform=_pct(3),
                description="Industrial production 3-month momentum.",
            ),
            _single(
                series_map, "real_income_ex_transfers", config,
                name="Real Income ex Transfers YoY",
                tier="coincident",
                family="income",
                transform=_pct(12),
                description="Real personal income excluding current transfers.",
            ),
            _single(
                series_map, "real_income_ex_transfers", config,
                name="Real Income ex Transfers 3M",
                tier="coincident",
                family="income",
                transform=_pct(3),
                description="3-month real-income momentum.",
            ),
            _single(
                series_map, "real_mfg_trade_sales", config,
                name="Real Manufacturing & Trade Sales YoY",
                tier="coincident",
                family="sales",
                transform=_pct(12),
                description="Real manufacturing and trade sales versus year ago.",
            ),
            _single(
                series_map, "real_mfg_trade_sales", config,
                name="Real Manufacturing & Trade Sales 3M",
                tier="coincident",
                family="sales",
                transform=_pct(3),
                description="3-month real sales momentum.",
            ),
        ]
    )

    # ----------------------------
    # LAGGING
    # ----------------------------
    features.extend(
        [
            _single(
                series_map, "cpi", config,
                name="CPI YoY",
                tier="lagging",
                family="inflation",
                transform=_pct(12),
                description="Headline inflation; descriptive lagging-cycle heat.",
            ),
            _single(
                series_map, "core_cpi", config,
                name="Core CPI YoY",
                tier="lagging",
                family="inflation",
                transform=_pct(12),
                description="Core inflation; descriptive lagging-cycle heat.",
            ),
            _single(
                series_map, "fed_funds", config,
                name="Fed Funds Level",
                tier="lagging",
                family="policy_rates",
                transform=_level,
                description="Policy-rate level; lagging descriptor, not regime driver.",
            ),
            _single(
                series_map, "us10y", config,
                name="US10Y Level",
                tier="lagging",
                family="long_yields",
                transform=_level,
                description="Long-yield level; lagging descriptor, not regime driver.",
            ),
        ]
    )

    # ----------------------------
    # IMMINENT / DIAGNOSTIC
    # ----------------------------
    features.extend(
        [
            _single(
                series_map, "us2y", config,
                name="US2Y Change 4W",
                tier="imminent",
                family="rates_transition",
                transform=_diff(4),
                description="Rapid short-rate decline can become late-slowdown evidence.",
            ),
            _single(
                series_map, "us2y", config,
                name="US2Y Change 13W",
                tier="imminent",
                family="rates_transition",
                transform=_diff(13),
                description="Persistent short-rate decline; phase-conditional only.",
            ),
            _single(
                series_map, "unemployment", config,
                name="Unemployment 6M Change",
                tier="imminent",
                family="labor_transition",
                transform=_diff(6),
                description="Broader unemployment deterioration.",
                orientation=-1.0,
            ),
            _single(
                series_map, "continuing_claims", config,
                name="Continuing Claims 13W",
                tier="imminent",
                family="labor_transition",
                transform=_pct(13),
                description="Rising continuing claims indicate weaker re-employment.",
                orientation=-1.0,
            ),
            _single(
                series_map, "high_yield_oas", config,
                name="High Yield OAS 13W",
                tier="imminent",
                family="credit_transition",
                transform=_diff(13),
                description="Spread widening is credit deterioration.",
                orientation=-1.0,
            ),
            _single(
                series_map, "nfci", config,
                name="NFCI 13W Change",
                tier="imminent",
                family="credit_transition",
                transform=_diff(13),
                description="Rising NFCI = tightening financial conditions.",
                orientation=-1.0,
            ),
        ]
    )

    # ----------------------------
    # LIQUIDITY MODIFIER
    # ----------------------------
    features.extend(
        [
            _single(
                series_map, "m2", config,
                name="M2 YoY",
                tier="liquidity",
                family="policy_liquidity",
                transform=_pct(12),
                description="Money-supply growth; modifier only.",
            ),
            _single(
                series_map, "m2", config,
                name="M2 3M",
                tier="liquidity",
                family="policy_liquidity",
                transform=_pct(3),
                description="Shorter money-supply momentum; modifier only.",
            ),
            _single(
                series_map, "fed_assets", config,
                name="Fed Assets 13W",
                tier="liquidity",
                family="policy_liquidity",
                transform=_pct(13),
                description="Federal Reserve balance-sheet momentum.",
            ),
            _single(
                series_map, "bank_loans", config,
                name="Bank Loans YoY",
                tier="liquidity",
                family="credit_liquidity",
                transform=_pct(52),
                description="Private credit growth; liquidity modifier.",
            ),
            _single(
                series_map, "nfci", config,
                name="NFCI Level",
                tier="liquidity",
                family="credit_liquidity",
                transform=_level,
                description="Positive NFCI = tighter-than-average conditions.",
                orientation=-1.0,
                direct=(0.0, 0.75),
            ),
            _single(
                series_map, "high_yield_oas", config,
                name="High Yield OAS Level",
                tier="liquidity",
                family="credit_liquidity",
                transform=_level,
                description="Higher HY spreads = tighter credit liquidity.",
                orientation=-1.0,
            ),
            _single(
                series_map, "vix", config,
                name="VIX Level",
                tier="liquidity",
                family="market_liquidity",
                transform=_level,
                description="Higher volatility = weaker market liquidity.",
                orientation=-1.0,
            ),
            _single(
                series_map, "vix", config,
                name="VIX 4W Change",
                tier="liquidity",
                family="market_liquidity",
                transform=_diff(4),
                description="Rising volatility = tightening market liquidity.",
                orientation=-1.0,
            ),
        ]
    )

    return {
        item.spec.name: item
        for item in features
        if item is not None and not item.frame.empty
    }


def align_features_weekly(
    features: dict[str, FeatureFrame],
    *,
    as_of: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = []
    for item in features.values():
        vals = pd.to_datetime(
            item.frame["availability_date"],
            errors="coerce",
        ).dropna()
        dates.extend(vals.tolist())

    if not dates:
        return pd.DataFrame(), pd.DataFrame()

    end = (
        pd.Timestamp(as_of).normalize()
        if as_of is not None
        else pd.Timestamp.today().normalize()
    )
    start = min(dates)
    grid = pd.date_range(start, end, freq="W-FRI")

    scores = pd.DataFrame(index=grid)
    raws = pd.DataFrame(index=grid)

    left = pd.DataFrame({"grid_date": grid})

    for name, item in features.items():
        work = item.frame.copy()
        work["availability_date"] = pd.to_datetime(
            work["availability_date"], errors="coerce"
        )
        work = (
            work.dropna(subset=["availability_date"])
            .sort_values("availability_date")
        )
        work = work[work["availability_date"] <= end]
        if work.empty:
            continue

        right = work[
            ["availability_date", "score", "raw"]
        ].rename(
            columns={"availability_date": "known_at"}
        )

        merged = pd.merge_asof(
            left,
            right.sort_values("known_at"),
            left_on="grid_date",
            right_on="known_at",
            direction="backward",
            allow_exact_matches=True,
        ).set_index("grid_date")

        scores[name] = merged["score"].reindex(grid)
        raws[name] = merged["raw"].reindex(grid)

    scores.index.name = "date"
    raws.index.name = "date"
    return scores, raws
