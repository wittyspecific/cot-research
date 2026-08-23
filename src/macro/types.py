
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    series_id: str
    label: str
    frequency: str
    release_lag_days: int
    history_start: str
    required: bool = True
    enabled: bool = True
    provider: str = "FRED"
    note: str = ""


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    tier: str
    family: str
    source_keys: tuple[str, ...]
    description: str


@dataclass
class AtomicModelResult:
    name: str
    tier: str
    family: str
    score: float | None
    signal: str
    confidence: float
    persistence_13w: float
    raw_value: float | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TierSnapshot:
    tier: str
    index: float | None
    equilibrium: float | None
    distance: float | None
    slope_13w: float | None
    persistence: float
    families_available: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MacroNavigationResult:
    cycle_phase: str
    transition_state: str
    confidence: float
    as_of: str

    leading: TierSnapshot
    coincident: TierSnapshot
    lagging: TierSnapshot

    phase_divergence: str
    imminent_recession: dict[str, Any]
    model_breadth: dict[str, Any]
    liquidity_modifier: dict[str, Any]
    transition_models: dict[str, Any]
    macro_families: dict[str, Any]

    atomic_models: list[dict[str, Any]]
    family_consensus: list[dict[str, Any]]
    cycle_history: list[dict[str, Any]]
    historical_validation: dict[str, Any]

    drivers: list[str]
    data_quality: dict[str, Any]

    # Compatibility aliases for earlier Macro Model Library consumers.
    regime: str = ""
    leading_cycle_score: float | None = None
    coincident_cycle_score: float | None = None
    recession_transition_score: float | None = None
    cross_asset_confirmation_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
