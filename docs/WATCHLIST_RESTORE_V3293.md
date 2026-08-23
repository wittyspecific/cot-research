# V3.29.3 · Original Watchlist Logic Restored

## Entscheidung

Die V3.29-generierte generische COT-Scanner-Logik wird nicht länger als
primärer Opportunity-Discovery-Layer verwendet.

Stattdessen wird die bestehende `pages/watchlist.py` direkt innerhalb des
Opportunity Scanners ausgeführt.

Dadurch bleiben insbesondere die bereits etablierte Watchlist-Mechanik,
Macro-/Micro-COT-Zusammenführung, Signal-Age-/Freshness-Logik und die
bestehenden Watchlist-Klassifikationen unverändert maßgeblich.

## Architektur

Opportunity Scanner:

- Beobachtungsliste
  - direkte Ausführung der bestehenden `pages/watchlist.py`
  - keine nachgebaute Parallel-Logik
- Seasonality Scanner
  - weiterhin eigener Timing-/Turn-Layer

## Schutz

`pages/watchlist.py` und die Watchlist-Engines werden nicht verändert.
Der Installer speichert den SHA256 der originalen Watchlist und ein Test
stellt sicher, dass die Datei unverändert bleibt.
