
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from .types import SeriesSpec


# V3.24.0 deliberately uses public, directly reproducible series.
# Release lags are conservative "known-at" approximations and are NOT vintages.
SERIES_SPECS: tuple[SeriesSpec, ...] = (
    # Rates / curve
    SeriesSpec("us2y", "DGS2", "US 2-Year Treasury Yield", "daily", 1, "1960-01-01"),
    SeriesSpec("us10y", "DGS10", "US 10-Year Treasury Yield", "daily", 1, "1960-01-01"),
    SeriesSpec("us3m", "DGS3MO", "US 3-Month Treasury Yield", "daily", 1, "1960-01-01"),
    SeriesSpec("fed_funds", "DFF", "Federal Funds Effective Rate", "daily", 1, "1960-01-01"),

    # Ex-post evaluation label only. NEVER used as a model feature.
    SeriesSpec(
        "usrec",
        "USREC",
        "NBER based Recession Indicator",
        "monthly",
        0,
        "1960-01-01",
        required=False,
        note="Retrospective validation label only; excluded from all model features.",
    ),

    # Leading / labor
    SeriesSpec("initial_claims", "ICSA", "Initial Jobless Claims", "weekly", 5, "1960-01-01"),
    SeriesSpec("continuing_claims", "CCSA", "Continuing Claims", "weekly", 12, "1960-01-01"),
    SeriesSpec("unemployment", "UNRATE", "US Unemployment Rate", "monthly", 40, "1960-01-01"),
    SeriesSpec("payems", "PAYEMS", "Total Nonfarm Payrolls", "monthly", 40, "1960-01-01"),

    # Housing / orders / sentiment
    SeriesSpec("building_permits", "PERMIT", "Building Permits", "monthly", 50, "1960-01-01"),
    SeriesSpec("housing_starts", "HOUST", "Housing Starts", "monthly", 50, "1960-01-01"),
    SeriesSpec(
        "manufacturing_orders",
        "AMTMNO",
        "Manufacturers' New Orders: Total Manufacturing",
        "monthly",
        65,
        "1992-01-01",
    ),
    SeriesSpec(
        "consumer_sentiment",
        "UMCSENT",
        "University of Michigan Consumer Sentiment",
        "monthly",
        65,
        "1960-01-01",
        required=False,
        note="FRED distribution is delayed; optional leading-sentiment family.",
    ),

    # Coincident real economy
    SeriesSpec("industrial_production", "INDPRO", "Industrial Production", "monthly", 50, "1960-01-01"),
    SeriesSpec(
        "real_income_ex_transfers",
        "W875RX1",
        "Real Personal Income Excluding Current Transfer Receipts",
        "monthly",
        40,
        "1960-01-01",
    ),
    SeriesSpec(
        "real_mfg_trade_sales",
        "CMRMTSPL",
        "Real Manufacturing and Trade Industries Sales",
        "monthly",
        75,
        "1960-01-01",
    ),

    # Lagging
    SeriesSpec("cpi", "CPIAUCSL", "CPI All Items", "monthly", 20, "1960-01-01"),
    SeriesSpec("core_cpi", "CPILFESL", "Core CPI", "monthly", 20, "1960-01-01"),

    # Credit / liquidity modifier
    SeriesSpec(
        "high_yield_oas",
        "BAMLH0A0HYM2",
        "ICE BofA US High Yield OAS",
        "daily",
        1,
        "1996-01-01",
        required=False,
        note="Optional because FRED may expose limited current history.",
    ),
    SeriesSpec("nfci", "NFCI", "Chicago Fed National Financial Conditions Index", "weekly", 5, "1960-01-01"),
    SeriesSpec("bank_loans", "TOTLL", "Loans and Leases in Bank Credit", "weekly", 10, "1960-01-01"),
    SeriesSpec("m2", "M2SL", "M2 Money Stock", "monthly", 35, "1960-01-01"),
    SeriesSpec("fed_assets", "WALCL", "Federal Reserve Total Assets", "weekly", 2, "2003-01-01"),
    SeriesSpec(
        "vix",
        "VIXCLS",
        "CBOE Volatility Index: VIX",
        "daily",
        1,
        "1960-01-01",
        required=False,
    ),

    # V3.26.0 diagnostic macro families
    # Optional by design: these series do NOT enter the production Cycle vote.
    SeriesSpec(
        "labor_force",
        "CLF16OV",
        "Civilian Labor Force Level",
        "monthly",
        40,
        "1990-01-01",
        required=False,
        note="Diagnostic Labor Quality family only; excluded from Business Cycle vote.",
    ),
    SeriesSpec(
        "civilian_employment",
        "CE16OV",
        "Civilian Employment Level",
        "monthly",
        40,
        "1990-01-01",
        required=False,
        note="Diagnostic Labor Quality family only; excluded from Business Cycle vote.",
    ),
    SeriesSpec(
        "full_time_employment",
        "LNS12500000",
        "Employed, Usually Work Full Time",
        "monthly",
        40,
        "1990-01-01",
        required=False,
        note="Diagnostic Labor Quality family only; excluded from Business Cycle vote.",
    ),
    SeriesSpec(
        "civilian_population",
        "CNP16OV",
        "Civilian Noninstitutional Population",
        "monthly",
        40,
        "1990-01-01",
        required=False,
        note="Population denominator for diagnostic labor/housing normalization only.",
    ),
    SeriesSpec(
        "real_disposable_income",
        "DSPIC96",
        "Real Disposable Personal Income",
        "monthly",
        45,
        "1990-01-01",
        required=False,
        note="Diagnostic Household Resilience family only; excluded from Business Cycle vote.",
    ),
    SeriesSpec(
        "real_pce",
        "PCEC96",
        "Real Personal Consumption Expenditures",
        "monthly",
        45,
        "1990-01-01",
        required=False,
        note="Diagnostic Household Resilience family only; excluded from Business Cycle vote.",
    ),
    SeriesSpec(
        "personal_saving_rate",
        "PSAVERT",
        "Personal Saving Rate",
        "monthly",
        45,
        "1990-01-01",
        required=False,
        note="Household buffer context only; no mechanical family vote.",
    ),
    SeriesSpec(
        "avg_hourly_earnings",
        "CES0500000003",
        "Average Hourly Earnings, Total Private",
        "monthly",
        40,
        "1990-01-01",
        required=False,
        note="Used with CPI for diagnostic Real Wage growth only.",
    ),
)


DEFAULT_CONFIG: dict[str, Any] = {
    "cache": {
        "path": ".cache/macro_model_library/v3241_macro.sqlite3",
        "ttl_hours": 12.0,
        "timeout_seconds": 20.0,
    },
    "normalization": {
        "years": 10,
        "monthly_min_obs": 36,
        "weekly_min_obs": 104,
        "z_clip": 3.5,
    },
    "equilibrium": {
        "lookback_weeks": 520,
        "min_weeks": 156,
        "distance_threshold": 5.0,
        "slope_weeks": 13,
    },
    "phase": {
        "persistence_weeks": 4,
        "persistence_required": 3,
    },
    "breadth": {
        "atomic_threshold": 20.0,
        "family_agreement_threshold": 0.60,
        "family_confirmation_threshold": 0.70,
    },
    "imminent": {
        "short_rate_score": -35.0,
        "claims_score": -20.0,
        "labor_score": -20.0,
        "credit_score": -20.0,
        "restepening_bp": 50.0,
        "coincident_distance_watch": 10.0,
    },
    "tier_family_weights": {
        "leading": {
            "housing": 1.0,
            "orders": 1.0,
            "labor_leading": 1.0,
            "yield_curve": 1.0,
            "sentiment": 1.0,
        },
        "coincident": {
            "employment": 1.0,
            "production": 1.0,
            "income": 1.0,
            "sales": 1.0,
        },
        "lagging": {
            "inflation": 1.0,
            "policy_rates": 1.0,
            "long_yields": 1.0,
        },
    },
    "liquidity_weights": {
        "policy": 1.0,
        "credit": 1.0,
        "market": 1.0,
    },
}


@dataclass(frozen=True)
class MacroConfig:
    raw: dict[str, Any]
    source_path: Path | None = None

    def section(self, name: str) -> dict[str, Any]:
        return dict(self.raw.get(name, {}) or {})

    def nested(self, section: str, key: str) -> dict[str, float]:
        return {
            str(k): float(v)
            for k, v in dict(
                self.raw.get(section, {}).get(key, {}) or {}
            ).items()
        }


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None = None) -> MacroConfig:
    cfg_path = Path(path or "config/macro_model_library.toml")
    override: dict[str, Any] = {}

    if cfg_path.exists():
        if tomllib is None:
            raise RuntimeError("TOML configuration requires Python 3.11+.")
        with cfg_path.open("rb") as handle:
            override = dict(tomllib.load(handle) or {})

    return MacroConfig(
        raw=_deep_merge(DEFAULT_CONFIG, override),
        source_path=cfg_path if cfg_path.exists() else None,
    )
