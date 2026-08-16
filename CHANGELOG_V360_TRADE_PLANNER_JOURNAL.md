# V3.6.0 · Trade Planner & Journal Foundation

## Ziel
Die diskretionäre Supply-&-Demand-Entscheidung wird als reproduzierbarer Forward-Datensatz erfasst. Der Bot eröffnet weiterhin keine Trades.

## Neu
- Sidebar-Sektion `TRADING` mit `Trade Planner` und `Trading Journal`.
- Manuelle Eingaben: CFD-Symbol, Long/Short, Supply/Demand, Timeframe, Zone Low/High, Entry, Stop, Target, Freshness, Retests, Qualitätsnote, Plan-Typ REAL/SIMULATION/SKIPPED und Skip-Grund.
- Vollständiger Snapshot zum Planzeitpunkt:
  - Legacy COT inkl. Commercial/Non-Commercial/Retail Roh- und Perzentilwerte,
  - 4/4-Bestätigung, Positionierungszustand, Hedger Cycle, Commercial Range und Velocity,
  - moderner Managed-Money-/Leveraged-Funds-Flow inkl. robuster Divergenzwerte,
  - 20/40/60T sowie vollständige bestehende Saisonalitätsstatistik,
  - Preisproxy-Renditen und realisierte Volatilität,
  - MT5 CFD-Symbolspecs/Bid/Ask/Last,
  - Account-/Portfoliozustand und vollständige offene Positionen,
  - FTMO-/Risk-Desk-State und Pre-Trade Approval.
- FX-Paare speichern Base- und Quote-COT separat plus Pair Bias und Pair Seasonality.
- Manuelle COT-Marktzuordnung als Fallback für nicht automatisch aufgelöste CFDs.

## SQLite Datenmodell
Standardpfad auf macOS:
`~/Library/Application Support/COT Research/trading_journal.sqlite3`

Die Datenbank liegt absichtlich außerhalb des jeweiligen Download-Ordners und bleibt damit versionsübergreifend erhalten.

Tabellen:
- `trade_plans`: unveränderlicher Originalplan.
- `trade_snapshots`: unveränderlicher vollständiger JSON-Snapshot inkl. SHA-256-Hash.
- `snapshot_features`: normalisierte Long-Feature-Tabelle für spätere Statistik/ML.
- `trade_events`: append-only Änderungen/Entscheidungen nach dem Originalplan.
- `trade_outcomes`: getrennte, später aktualisierbare Markt-Outcomes (MAE/MFE/R etc.).
- `schema_meta`: Schema-Versionierung.

SQLite-Trigger verhindern nachträgliches UPDATE/DELETE von Plans, Snapshots, Features und Events.

## Noch nicht automatisch
Der automatische Outcome Tracker (Entry erreicht, SL/TP-Reihenfolge, MAE/MFE, +1R/+2R/+3R, Forward Returns) ist als Datenmodell vorbereitet, wird aber erst im nächsten Schritt an historische CFD-Preisdaten angebunden.

## Tests
- 107/107 Regressionstests erfolgreich.
- Neue Tests prüfen Datenbankintegrität, Snapshot-Hash, Immutability, append-only Events, mutable Outcomes, Feature-Flattening, FX-Kontext, Copper-Mapping und Navigation.
