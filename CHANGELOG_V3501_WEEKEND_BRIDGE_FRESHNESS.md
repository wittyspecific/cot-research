# V3.5.0.1 · MT5 Bridge Weekend Freshness Hotfix

## Problem

Die macOS-MT5-Bridge verwendete den von MQL5 `TimeCurrent()` exportierten Server-Zeitstempel als Heartbeat. Außerhalb der Handelszeiten kann dieser Zeitstempel unverändert bleiben, obwohl der EA seine lokalen CSV-Dateien weiterhin regelmäßig aktualisiert. Dadurch wurde eine aktive Bridge am Wochenende fälschlich als veraltet gemeldet.

## Fix

- Bridge-Freshness wird jetzt über die lokalen Änderungszeiten von `cot_mt5_account.csv` und `cot_mt5_positions.csv` geprüft.
- Die MT5-Serverzeit bleibt separat als `market_time` erhalten.
- Keine Änderung an Account-, Positions- oder Tradingdaten.
- Keine Order-/Modify-/Close-Funktionen hinzugefügt.
- Regressionstest für eine aktive Bridge bei 24 Stunden alter Marktzeit ergänzt.

## Tests

72/72 Tests erfolgreich.
