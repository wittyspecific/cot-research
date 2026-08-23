# V3.26.0 · Macro Transition & Family Layer

## Ziel

Diese Version ergänzt die bestehende Macro Model Library um eine transparente
Transition-/Family-Schicht. Sie verändert den produktiven Business-Cycle-Core
bewusst nicht.

Die Architektur bleibt:

Business Cycle Core → Transition Diagnostics → Imminent Recession →
Breadth/Scatter → Liquidity → bestehende COT/Seasonality/Market-Structure Layer.

## Neue Macro Families

### Labor Quality

- Full-Time Employment / Labor Force
- Employment / Labor Force
- Employment / Civilian Population
- Full-Time Employment / Employment

### Housing Activity Normalization

- Building Permits / Civilian Population
- Housing Starts / Civilian Population
- jeweils 6M-Veränderung

Das ist ein transparenter Aktivitäts-Proxy. Es wird ausdrücklich nicht behauptet,
dass Permits/Starts eine reine Nachfrage-Messung sind.

### Household Resilience

- Real Disposable Personal Income YoY
- Real Personal Consumption Expenditures YoY
- Real Hourly Earnings YoY
- Personal Saving Rate als Kontext ohne mechanische Stimme

## Neue Transition Models

- Housing → Labor
- Labor → Household
- Coincident → US 2Y

Alle Regeln sind Research-Diagnostik und verändern weder `cycle_phase` noch
Imminent-Recession, Breadth oder Liquidity.

Die Datenhistorie bleibt current/revised FRED mit konservativen Release-Lags.
Echte historische Point-in-Time-Validierung erfordert Vintage-Daten.

Es wird keine proprietäre Henrik-Zeberg-Formel, kein proprietäres Gewicht und
keine proprietäre Equilibrium-Konstruktion repliziert.
