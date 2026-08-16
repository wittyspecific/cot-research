# V3.6.0.1 · Full MT5 CFD Catalog

## Ziel
Trade Planner und Portfolio & Risk dürfen nicht von der manuellen Market-Watch-Auswahl abhängen.

## Änderungen
- `MT5ReadOnlyBridge.mq5` exportiert jetzt `SymbolsTotal(false)`: den vollständigen brokerseitigen MT5-Symbolkatalog statt nur `Market Watch`.
- Symbolmetadaten ergänzt: Description, Path, Market-Watch-Status, Visibility, Trade Mode und `can_open`.
- Für neue Trade-Pläne werden nur Symbole angeboten, die laut MT5 für neue Positionen geöffnet werden können; ausgeblendete, aber handelbare Symbole bleiben sichtbar.
- Der große Symbolkatalog wird standardmäßig nur alle 60 Sekunden aktualisiert; Account und offene Positionen bleiben im normalen 2-Sekunden-Takt.
- Trade Planner und Portfolio & Risk verwenden dieselbe zentrale Symbolnormalisierung und zeigen suchbare, beschreibende Labels.
- Direkter MT5-Python-Modus nutzt, sofern verfügbar, ebenfalls `symbols_get()` für den vollständigen Brokerkatalog.

## Keine Änderung
- Keine Order-/Modify-/Close-Funktion.
- COT-, Journal-, Risk- und Snapshot-Logik unverändert.
- Die bestehende Journal-SQLite-Datenbank bleibt erhalten.
