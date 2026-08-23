# V3.27.0 · Macro × COT Regime

`Macro × COT Regime` ist der verbindende Research-Layer zwischen der bestehenden Macro Model Library und der konkreten Asset-/Trade-Selektion. Er erzeugt keine Entries.

**Informationsfluss:** Business Cycle → Macro Momentum / Transition Risk → Macro × COT Divergence → Cross-Asset Positioning → Asset Bias / Setup Type → Technical Setup → Entry → Risk Management.

Die bestehende `src.macro.macro_model_library` bleibt alleiniger Business-Cycle-Driver. Die neue Engine leitet nur einen traderfreundlichen Sechs-Phasen-Read ab: Expansion, Late Expansion, Peak, Contraction, Trough, Early Expansion.

## COT Structural State

TFF nutzt **Asset Manager** als strukturellen institutionellen Block. Dealer/Intermediary wird ausdrücklich nicht als physischer Commercial Hedger interpretiert. Disaggregated nutzt **Producer / Merchant**.

COT-State berücksichtigt Net/OI-Level, 156W-Percentile, 1W/2W/4W-Flow, getrennte Long-/Short-Deltas, aktiven Positionsaufbau stärker als Unwinding und Persistenz. Die Flow-Gewichtung ist 4W > 2W > 1W. Eine einzelne Woche kann keinen starken Transition-State erzeugen.

## Transition Pressure

0–100 Research-Score, **keine Wahrscheinlichkeit**. Zentral in `config/macro_cot_regime.toml`: 30% COT Persistence, 25% Cross-Asset Breadth, 20% Macro Momentum / zweite Ableitung, 15% Leading Breadth, 10% Financial Market Confirmation. Fehlende Komponenten werden nicht erfunden; Confidence sinkt entsprechend.

## Cross-Asset Basket

S&P 500, Dow, JPY, CHF und US 10Y erhalten höhere Gewichte. Nasdaq, Gold, Copper, Crude und Cotton sind niedriger gewichtet. Natural Gas und Wheat sind V1 asset-specific und stimmen nicht automatisch im Risk-On/Risk-Off-Basket ab.

## Opportunity Map

Nur `FAVOR`, `WATCH`, `NEUTRAL`, `AVOID`, `CONFLICT`. Keine BUY-/SELL-Anweisung. Setup Types: CONFIRMED TREND, EARLY TRANSITION, MACRO-COT DIVERGENCE, PEAK REVERSAL, TROUGH REVERSAL, CONFLICT, NO EDGE.

## Typisierung

Der Bot ist Python/Streamlit. Die gewünschte saubere Typisierung wird als Python-Dataclasses + Type Hints umgesetzt. Keine parallele TypeScript-/React-Schicht.

## Mock / Fallback

Produktionscode verwendet keine Mock-Fallbacks. Der Konzept-Beispielzustand existiert nur in Unit-Tests zur State-Machine-Validierung.
