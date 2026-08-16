# V3.8.1.4.1 · Outcome State Guard

Hotfix gegen Status-Regressionen im Outcome Tracker.

- Ein bestätigter `ACTIVE`-Trade darf durch fehlende oder noch nicht abgeschlossene History niemals wieder `PLANNED` oder `EXPIRED` werden.
- Bereits gespeicherter Fill, Entry-Zeit, MFE/MAE und weitere Outcome-Daten bleiben bei einem geblockten Rückschritt erhalten.
- `ACTIVE -> CLOSED` und `ACTIVE -> AMBIGUOUS` bleiben weiterhin zulässige Fortschritte.
- Sync-Ergebnis meldet `state_regressions_blocked` für Diagnose/Audit.
- Kein MT5-Bridge-Update erforderlich.
