# V3.29.0.1 · Research Panel V1 · Actual-State Migration

## Leitidee

**Data → Interpretation → Regime → Bias → Opportunity**

Das Research Panel wird auf vier Kernseiten reduziert:

1. Opportunity Scanner
2. Marktanalyse
3. Währungsstärke
4. Makro-Regime

Bestehende Research-Engines werden nicht gelöscht. Alte Detailseiten bleiben unter **Advanced** über geschützte Wrapper erreichbar.

## Opportunity Scanner

Tabs: **COT Scanner** und **Seasonality Scanner**. Der COT Scanner zeigt strukturellen Bias, Mikro-COT, 156W-Struktur, 26W-COT-Index, 1W/2W/4W-Flow, Setup-Stärke und Release-Status. Der Seasonality Scanner zeigt Turn, Distanz, Robustheit und 20/40/60T-Richtung.

## Marktanalyse

Tabs: **Overview, COT, Seasonal Turn, Historical Analog, Market Context**. Historische Analogs werden erst auf Anforderung berechnet. FX-Paare verwenden automatisch die relative FX-COT-Analog-Engine.

## Währungsstärke

Tabs: **Currency Ranking** und **Pair Opportunities**. Nicht-USD-Währungen werden über ihre TFF-Futures relativ zum USD gelesen. USD ist eine transparente Null-Basis im Pair-Ranking und kein erfundener COT-Report.

## Makro-Regime

Tabs: **Overview, Business Cycle, Macro × COT, Risk Conditions**. Business Cycle und Macro × COT werden in einer Trader-Ansicht gebündelt, ohne die Engines zu verschmelzen.

## State Layer

Die Streamlit-App bleibt Python-basiert. Statt einer parallelen TypeScript-/React-Schicht nutzt V1 typisierte Python-Dataclasses:

- `CotPositioningState`
- `SeasonalTurnState`
- `HistoricalAnalogState`
- `MarketContextState`
- `TradeOpportunityState`
- `MacroRegimeState`

## Setup Types

- CONFIRMED TREND
- EARLY TRANSITION
- MACRO-COT DIVERGENCE
- PEAK REVERSAL
- TROUGH REVERSAL
- CONFLICT
- NO EDGE

Transition Trades werden separat klassifiziert, aber nicht pauschal schlechter behandelt.

## Datenqualität

Kein Mock-Fallback. Fehlende oder schwache Daten werden explizit als `Insufficient Data`, `Low Confidence` oder `No Current Signal` dargestellt.

## Dark Theme

Das neue zentrale Theme liegt in `src/trader_theme.py` und wird zusätzlich in `app.py` geladen. Es verändert nur die Darstellung, nicht die Modelllogik.
