# V3.6.2 · Multi-Trader Foundation

## Ziel
Mehrere Trader können denselben lokalen Simulator und Outcome Tracker verwenden, ohne dass ihre Trade-Pläne vermischt werden.

## Neu
- Lokales Trader-Login mit `ADMIN`- und `TRADER`-Rolle.
- Passwörter werden ausschließlich als PBKDF2-SHA256-Hash mit individuellem Salt gespeichert.
- Neue SQL-Tabelle `traders`.
- `trade_plans` erhält eine stabile `trader_id`.
- Bestehende Pläne aus V3.6.1 können beim ersten Admin-Setup einmalig dem ersten Admin zugeordnet werden.
- Trading Journal kann als ADMIN alle Trader oder einen einzelnen Trader anzeigen.
- Normale TRADER sehen ausschließlich ihre eigenen Trade-Pläne, Events, Outcomes und Feature-Exporte.
- Outcome Tracker kann traderbezogen synchronisieren; alle verwenden weiterhin dieselbe lokale MT5-Kurshistorie.
- Normale TRADER sehen weder Risk Cockpit noch Portfolio & Risk noch die Trader-Verwaltung.
- Trader-Snapshots speichern keine privaten FTMO-Account-, Open-Position- oder Portfolio-Risk-Daten des ADMIN.
- Neue Admin-Seite zum Anlegen, Aktivieren/Deaktivieren und Zurücksetzen von Trader-Passwörtern.

## Datenprinzip
Trader-Identität wird getrennt von Plan-Time-Features geführt. `trader_id` bleibt Metadatum und wird nicht automatisch als ML-Feature interpretiert.

## Unverändert
- MT5-Bridge bleibt read-only.
- Outcome-Tracker-Logik M5 → M1 Fallback bleibt unverändert.
- COT-, Seasonality-, Risk- und Research-Methodik bleibt unverändert.
