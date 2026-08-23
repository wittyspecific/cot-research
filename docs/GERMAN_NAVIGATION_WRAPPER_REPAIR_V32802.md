# V3.28.0.2 · Navigation Wrapper Repair

## Warum ein zweiter Repair?

Die ersten beiden V3.28-Reparaturen versuchten, einen bestehenden Advanced-Guard
direkt in bereits existierende Research-Seiten einzufügen.

Das ist unnötig riskant, weil Guard-Code eigene Imports, Hilfsvariablen oder
mehrzeilige Kontrollblöcke besitzen kann.

## Neue Strategie

Die Originalseiten werden **nicht verändert**.

Für die drei Diagnose-Seiten werden kleine Advanced-Wrapper angelegt:

- `advanced_market_regime.py` → `market_regime.py`
- `advanced_credit_stress.py` → `credit_stress.py`
- `advanced_seasonality_edge_lab.py` → `seasonality_edge_lab.py`

Jeder Wrapper enthält den bereits funktionierenden Advanced-Guard aus einer
bestehenden Advanced-Seite und führt die Originalseite erst nach erfolgreichem
Guard aus.

## Vorteil

- keine Guard-Injektion in bestehende Seiten
- bestehende Diagnose-Seiten bleiben unverändert
- Advanced-IP-Schutz bleibt erhalten
- Navigation wird trotzdem schlanker
- Modell-/Trading-Code bleibt unangetastet

## Sichtbare Navigation

Die Navigationstitel werden zunächst deutsch vereinheitlicht. Die
vollständige Übersetzung der Inhalte einzelner Seiten kann danach separat und
kontrolliert erfolgen.
