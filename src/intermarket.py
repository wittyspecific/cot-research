from __future__ import annotations
# V3.15.5 · V3154 SOURCE CONTRACT COMPAT

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from .watchlist_macro_micro import classify_macro_micro_trade


@dataclass(frozen=True)
class IntermarketRelationship:
    currency_market: str
    currency_symbol: str
    reference_market: str
    reference_symbol: str
    polarity: int
    weight: str
    rationale: str
    category: str = "CURRENCY_COMMODITY"
    regime_dependent: bool = False
    currency_aliases: tuple[str, ...] = ()
    reference_aliases: tuple[str, ...] = ()

    @property
    def relationship_label(self) -> str:
        return "POSITIV" if int(self.polarity) > 0 else "NEGATIV"

    @property
    def left_aliases(self) -> tuple[str, ...]:
        return (self.currency_market, *self.currency_aliases)

    @property
    def right_aliases(self) -> tuple[str, ...]:
        return (self.reference_market, *self.reference_aliases)


# V3.15.4 historical core: intentionally kept stable for backwards-compatible tests.
CORE_RELATIONSHIPS: tuple[IntermarketRelationship, ...] = (
    IntermarketRelationship(
        currency_market="Canadian Dollar",
        currency_symbol="CAD",
        reference_market="WTI Crude Oil",
        reference_symbol="CL",
        polarity=1,
        weight="SEHR HOCH",
        rationale=(
            "Kanada ist ein großer Energieexporteur; Öl ist der primäre "
            "Commodity-Kontext für CAD."
        ),
        category="CURRENCY_COMMODITY",
        currency_aliases=("Kanadischer Dollar",),
        reference_aliases=("Crude Oil", "Rohöl WTI", "WTI"),
    ),
    IntermarketRelationship(
        currency_market="Australian Dollar",
        currency_symbol="AUD",
        reference_market="Copper",
        reference_symbol="HG",
        polarity=1,
        weight="HOCH",
        rationale=(
            "Copper dient als liquider Proxy für Industrial Metals sowie "
            "China- und globalen Rohstoffzyklus."
        ),
        category="CURRENCY_COMMODITY",
        currency_aliases=("Australischer Dollar",),
        reference_aliases=("Kupfer",),
    ),
    IntermarketRelationship(
        currency_market="Japanese Yen",
        currency_symbol="JPY",
        reference_market="WTI Crude Oil",
        reference_symbol="CL",
        polarity=-1,
        weight="MITTEL",
        rationale=(
            "Japan ist Netto-Energieimporteur; steigende Energiepreise wirken "
            "tendenziell gegen den JPY-Terms-of-Trade-Kontext."
        ),
        category="CURRENCY_COMMODITY",
        currency_aliases=("Japanischer Yen",),
        reference_aliases=("Crude Oil", "Rohöl WTI", "WTI"),
    ),
)


# V3.15.5 expanded COT-to-COT research universe.
INTERMARKET_RELATIONSHIPS: tuple[IntermarketRelationship, ...] = (
    CORE_RELATIONSHIPS[0],  # CAD ↔ WTI +
    CORE_RELATIONSHIPS[1],  # AUD ↔ Copper +
    CORE_RELATIONSHIPS[2],  # JPY ↔ WTI -
    IntermarketRelationship(
        currency_market="Swiss Franc",
        currency_symbol="CHF",
        reference_market="Gold",
        reference_symbol="GC",
        polarity=1,
        weight="MITTEL",
        rationale=(
            "CHF und Gold können denselben Safe-Haven-, USD- und Realzins-Kontext "
            "reflektieren; die Beziehung ist deutlich regimeabhängiger als CAD↔WTI."
        ),
        category="CURRENCY_COMMODITY",
        regime_dependent=True,
        currency_aliases=("Schweizer Franken", "Swiss Francs"),
    ),
    IntermarketRelationship(
        currency_market="US Dollar Index",
        currency_symbol="DX",
        reference_market="Gold",
        reference_symbol="GC",
        polarity=-1,
        weight="HOCH",
        rationale=(
            "Gold und der USD-Index zeigen häufig einen gegenläufigen monetären "
            "und Bewertungs-Kontext."
        ),
        category="MACRO_COMMODITY",
        currency_aliases=("US-Dollar-Index", "U.S. Dollar Index", "Dollar Index"),
    ),
    IntermarketRelationship(
        currency_market="US Dollar Index",
        currency_symbol="DX",
        reference_market="Copper",
        reference_symbol="HG",
        polarity=-1,
        weight="MITTEL",
        rationale=(
            "Copper ist ein globaler Growth-/China-Proxy; ein starker USD wirkt "
            "häufig gegen den Industrial-Metals-Komplex."
        ),
        category="MACRO_COMMODITY",
        regime_dependent=True,
        currency_aliases=("US-Dollar-Index", "U.S. Dollar Index", "Dollar Index"),
        reference_aliases=("Kupfer",),
    ),
    IntermarketRelationship(
        currency_market="Gold",
        currency_symbol="GC",
        reference_market="Silver",
        reference_symbol="SI",
        polarity=1,
        weight="HOCH",
        rationale=(
            "Gold und Silver gehören zum Precious-Metals-Komplex und bestätigen "
            "häufig denselben übergeordneten COT-Regimekontext."
        ),
        category="COMMODITY_COMMODITY",
        reference_aliases=("Silber",),
    ),
    IntermarketRelationship(
        currency_market="Gold",
        currency_symbol="GC",
        reference_market="US Treasury 10Y",
        reference_symbol="ZN",
        polarity=1,
        weight="MITTEL",
        rationale=(
            "Bullishe Treasury-Futures entsprechen typischerweise fallenden Renditen, "
            "was Gold häufig unterstützt; Beziehung ist regimeabhängig."
        ),
        category="COMMODITY_RATES",
        regime_dependent=True,
        reference_aliases=(
            "U.S. Treasury 10Y",
            "10-Year U.S. Treasury Notes",
            "US Treasury 10Y Note",
            "10Y Treasury",
        ),
    ),
    IntermarketRelationship(
        currency_market="E-mini S&P 500",
        currency_symbol="ES",
        reference_market="VIX",
        reference_symbol="VX",
        polarity=-1,
        weight="SEHR HOCH",
        rationale=(
            "Equity-Risk-On und implizite Volatilität stehen strukturell häufig "
            "gegenläufig zueinander."
        ),
        category="RISK_SENTIMENT",
        currency_aliases=("S&P 500", "E-mini S&P", "S&P 500 E-mini"),
        reference_aliases=("CBOE VIX", "Volatility Index", "VIX Futures"),
    ),
    IntermarketRelationship(
        currency_market="E-mini Nasdaq 100",
        currency_symbol="NQ",
        reference_market="VIX",
        reference_symbol="VX",
        polarity=-1,
        weight="HOCH",
        rationale=(
            "Nasdaq-Risk-On und Volatilität stehen häufig gegenläufig; der "
            "Zusammenhang wird nur als Confluence und nicht als Entry-Regel genutzt."
        ),
        category="RISK_SENTIMENT",
        currency_aliases=("Nasdaq 100", "E-mini Nasdaq", "Nasdaq"),
        reference_aliases=("CBOE VIX", "Volatility Index", "VIX Futures"),
    ),
)


def _direction_label(direction: int) -> str:
    value = int(direction or 0)
    if value > 0:
        return "BULLISH"
    if value < 0:
        return "BEARISH"
    return "NEUTRAL"


def _exact_match(series: pd.Series, candidates: tuple[str, ...]) -> pd.Series:
    normalized = {str(value).strip().upper() for value in candidates if str(value).strip()}
    return series.astype(str).str.strip().str.upper().isin(normalized)


def _find_market_row(
    all_markets: pd.DataFrame,
    market_name: str,
    *,
    aliases: tuple[str, ...] = (),
    symbol: str = "",
) -> pd.Series | None:
    """Resolve a COT market robustly across German/English labels and symbols."""
    if all_markets is None or all_markets.empty:
        return None

    names = (str(market_name), *tuple(aliases))
    if "market_name" in all_markets.columns:
        matches = all_markets[_exact_match(all_markets["market_name"], names)]
        if not matches.empty:
            return matches.iloc[-1]

    symbol_candidates = tuple(
        value for value in (str(symbol or "").strip(),) if value
    )
    if symbol_candidates:
        for column in ("ticker", "symbol", "market_symbol", "cfd_symbol"):
            if column not in all_markets.columns:
                continue
            matches = all_markets[
                _exact_match(all_markets[column], symbol_candidates)
            ]
            if not matches.empty:
                return matches.iloc[-1]

    return None


def relationship_alignment(
    currency_direction: int,
    reference_direction: int,
    polarity: int,
) -> str:
    """Return SUPPORT / CONFLICT / NEUTRAL for one COT horizon."""
    left = int(currency_direction or 0)
    right = int(reference_direction or 0)
    polarity = 1 if int(polarity or 0) >= 0 else -1

    if left == 0 or right == 0:
        return "NEUTRAL"

    expected_right = left * polarity
    return "SUPPORT" if right == expected_right else "CONFLICT"


def overall_alignment(macro: str, micro: str) -> str:
    macro = str(macro or "NEUTRAL").upper()
    micro = str(micro or "NEUTRAL").upper()

    if macro == "SUPPORT" and micro == "SUPPORT":
        return "STRONG SUPPORT"
    if {macro, micro} == {"SUPPORT", "CONFLICT"}:
        return "MIXED"
    if "SUPPORT" in {macro, micro} and "CONFLICT" not in {macro, micro}:
        return "SUPPORT"
    if "CONFLICT" in {macro, micro} and "SUPPORT" not in {macro, micro}:
        return "CONFLICT"
    return "NEUTRAL"


def evaluate_relationship(
    all_markets: pd.DataFrame,
    relationship: IntermarketRelationship,
) -> dict[str, Any]:
    left_row = _find_market_row(
        all_markets,
        relationship.currency_market,
        aliases=relationship.currency_aliases,
        symbol=relationship.currency_symbol,
    )
    right_row = _find_market_row(
        all_markets,
        relationship.reference_market,
        aliases=relationship.reference_aliases,
        symbol=relationship.reference_symbol,
    )

    base = {
        "currency_market": relationship.currency_market,
        "currency_symbol": relationship.currency_symbol,
        "reference_market": relationship.reference_market,
        "reference_symbol": relationship.reference_symbol,
        "polarity": int(relationship.polarity),
        "relationship": relationship.relationship_label,
        "weight": relationship.weight,
        "rationale": relationship.rationale,
        "category": relationship.category,
        "regime_dependent": bool(relationship.regime_dependent),
        "available": False,
        "error": "",
    }

    if left_row is None or right_row is None:
        missing = []
        if left_row is None:
            missing.append(relationship.currency_market)
        if right_row is None:
            missing.append(relationship.reference_market)
        return {
            **base,
            "error": "Fehlende COT-Daten: " + ", ".join(missing),
            "macro_alignment": "NEUTRAL",
            "micro_alignment": "NEUTRAL",
            "overall": "NEUTRAL",
        }

    currency_decision = classify_macro_micro_trade(left_row)
    reference_decision = classify_macro_micro_trade(right_row)

    left_macro = dict(currency_decision.get("macro") or {})
    right_macro = dict(reference_decision.get("macro") or {})
    left_micro = dict(currency_decision.get("micro") or {})
    right_micro = dict(reference_decision.get("micro") or {})

    left_macro_direction = int(left_macro.get("direction", 0) or 0)
    right_macro_direction = int(right_macro.get("direction", 0) or 0)
    left_micro_direction = int(left_micro.get("direction", 0) or 0)
    right_micro_direction = int(right_micro.get("direction", 0) or 0)

    macro_alignment = relationship_alignment(
        left_macro_direction,
        right_macro_direction,
        relationship.polarity,
    )
    micro_alignment = relationship_alignment(
        left_micro_direction,
        right_micro_direction,
        relationship.polarity,
    )

    return {
        **base,
        "available": True,
        "currency_macro_direction": left_macro_direction,
        "currency_macro_label": str(
            left_macro.get("label")
            or _direction_label(left_macro_direction)
        ),
        "currency_macro_phase": str(left_macro.get("phase", "") or ""),
        "reference_macro_direction": right_macro_direction,
        "reference_macro_label": str(
            right_macro.get("label")
            or _direction_label(right_macro_direction)
        ),
        "reference_macro_phase": str(right_macro.get("phase", "") or ""),
        "macro_alignment": macro_alignment,
        "currency_micro_direction": left_micro_direction,
        "currency_micro_label": _direction_label(left_micro_direction),
        "currency_micro_age_weeks": int(left_micro.get("age_weeks", -1) or -1),
        "currency_micro_fresh": bool(left_micro.get("fresh", False)),
        "reference_micro_direction": right_micro_direction,
        "reference_micro_label": _direction_label(right_micro_direction),
        "reference_micro_age_weeks": int(right_micro.get("age_weeks", -1) or -1),
        "reference_micro_fresh": bool(right_micro.get("fresh", False)),
        "micro_alignment": micro_alignment,
        "overall": overall_alignment(macro_alignment, micro_alignment),
    }


def evaluate_relationships(
    all_markets: pd.DataFrame,
    relationships: Iterable[IntermarketRelationship] = INTERMARKET_RELATIONSHIPS,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            evaluate_relationship(all_markets, relationship)
            for relationship in relationships
        ]
    )


def evaluate_core_relationships(
    all_markets: pd.DataFrame,
    relationships: Iterable[IntermarketRelationship] = CORE_RELATIONSHIPS,
) -> pd.DataFrame:
    """Backwards-compatible V3.15.4 entry point."""
    return evaluate_relationships(all_markets, relationships)


def relationship_matrix(
    relationships: Iterable[IntermarketRelationship] = INTERMARKET_RELATIONSHIPS,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "currency_market": item.currency_market,
                "currency_symbol": item.currency_symbol,
                "reference_market": item.reference_market,
                "reference_symbol": item.reference_symbol,
                "relationship": item.relationship_label,
                "weight": item.weight,
                "category": item.category,
                "regime_dependent": bool(item.regime_dependent),
                "rationale": item.rationale,
            }
            for item in relationships
        ]
    )
