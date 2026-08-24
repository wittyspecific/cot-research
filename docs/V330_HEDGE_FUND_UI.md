# V3.30 · Hedge Fund UI

## Ziel

Die Oberfläche wird ab V3.30 nicht mehr als Sammlung einzelner Streamlit-
Styles behandelt, sondern als ein zentrales institutionelles UI-System.

Die Research- und Trading-Logik bleibt davon getrennt.

## Design Tokens

- Background: `#081018`
- Surface: `#0D1722`
- Raised Surface: `#111D29`
- Border: `#22303D`
- Primary Text: `#F3F6FB`
- Secondary Text: `#95A3B3`
- Research Blue: `#62A6C9`
- Bullish: `#65D98B`
- Bearish: `#FF7373`
- Watch: `#F2B84B`
- Transition: `#79B8FF`

## Architektur

`src/ui/hedgefund.py`

liefert:

- globale Hedge-Fund-Theme-Schicht
- Page Header
- Section Header
- Metric Grid
- Status Chip
- Callout
- Divider
- zentrale Farbpalette

`src/style.py` und `src/trader_theme.py` rufen diese Schicht zuletzt auf.
Dadurch erhalten sowohl Legacy-Seiten als auch die neuen Research-Seiten
dieselbe Designsprache.

## Reihenfolge der Migration

1. Opportunity Scanner / COT Watchlist
2. Marktanalyse
3. Makro-Regime
4. Währungsstärke
5. Dashboard / Login / Sidebar
6. Advanced-Seiten nur soweit sinnvoll

## Wichtiger Schutz

V3.30.0 ändert keine COT-, Macro-, Seasonality-, Analog-, Risk- oder
Execution-Engine. Die visuelle Migration wird strikt von der Modellprüfung
getrennt.

Nach Abschluss der UI-Migration folgt ein separater Modell-Audit:
- welche Modelle sind produktiv
- welche Modelle sind nur Research
- Überschneidungen / redundante Scores
- Eingabedaten und Frequenzen
- Signalhierarchie
- Validierung / Backtest-Status
