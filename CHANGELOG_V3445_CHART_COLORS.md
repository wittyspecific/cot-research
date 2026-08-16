# V3.4.4.5 · Semantic Chart Colors

## Änderung

Alle Plotly-Charts verwenden jetzt eine zentrale, kontrastreiche Farbpalette.
Die Farben sind semantisch und bleiben über alle Diagramme hinweg konsistent:

- Commercial: Cyan (`#19C7FF`)
- Non-Commercial: Orange (`#FF9D00`)
- Retail / Non-Reportable: Lime-Grün (`#9BE600`)
- Moderner spekulativer Flow: Violett (`#B887FF`)
- Preis: nahezu Weiß (`#F2F6FC`)

Bestehende Linienstile wie solid / dash / dot bleiben erhalten. Unbekannte
Mehrfachreihen (z. B. Saisonfenster oder Research-Vergleiche) nutzen eine
zentrale High-Contrast-Colorway.

## Unverändert

- COT-, Netto-, NC- und Seasonality-Berechnungen
- Preis-/COT-Ausrichtung
- TradingView-artige Y-Achsen-Skalierung
- X-Achsen-Zoom, Pan und Zeitraumwahl
- zugrunde liegende Daten
