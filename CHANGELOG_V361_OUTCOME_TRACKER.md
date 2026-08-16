# V3.6.1 · MT5 Outcome Tracker

- Read-only MT5-History Request/Response über `Terminal\Common\Files`
- `CopyRates` für M5, M1 und D1; keine Orderfunktionen
- LIMIT/MARKET im Trade Planner
- optionales Limit-Expiry
- Lifecycle: PLANNED / ACTIVE / CLOSED / EXPIRED / AMBIGUOUS
- chronologische SL/TP-Auswertung
- M1-Fallback bei M5-Intrabar-Ambiguität
- MAE / MFE und +1R / +2R / +3R Zeitpunkte
- direction-adjusted 1/3/5/10/20/40/60 Trading-Day Forward Returns
- Journal Auto-Catch-up beim ersten Öffnen plus manueller Sync
- persistente SQLite-Migration von Schema v1 auf v2
- Trade-Pläne und Snapshots bleiben immutable; Outcomes bleiben separat mutable
