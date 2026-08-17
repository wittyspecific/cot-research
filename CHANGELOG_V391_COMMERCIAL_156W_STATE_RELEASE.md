# V3.9.1 · Commercial 156W State & Release Engine

## Ziel

Die primäre COT-Logik trennt jetzt konsequent **Zustand**, **Transition** und **Signal**. Das Commercial Net Percentile über 156 Wochen bleibt der zentrale sichtbare Positionierungswert. Der 26W COT-Index wird weiterhin berechnet und gespeichert, ist aber nur noch Advanced-/Research-Kontext.

## Primäre Logik

- `Commercial Net Percentile 156W >= 80` → `FULL HEDGE` (Zustand, kein bullishes Signal)
- `Commercial Net Percentile 156W <= 20` → `LOW HEDGE` (Zustand, kein bärisches Signal)
- Bewegung innerhalb der Extremzone wird über `Δ1W`, `Δ4W`, `Δ8W`, Episoden-Extrem und Extremdauer erfasst.
- Rücklauf innerhalb der Zone → `EARLY RELEASE · STILL EXTREME`, weiterhin kein Richtungs-Signal.
- Verlassen des oberen Extrembereichs nach unten → `BULLISH RELEASE`.
- Verlassen des unteren Extrembereichs nach oben → `BEARISH RELEASE`.
- Ein Release bleibt für die konfigurierte Release-Periode aktiv.

## Bestätigung

Beim Release liegt das aktuelle Commercial-Perzentil definitionsgemäß bereits außerhalb der Extremzone. Die Commercial-Bestätigung referenziert deshalb das **eingefrorene 156W-Extrem der vorausgegangenen Episode**. Retail/NC/Spec Flow bleiben Bestätigungs- und Kontextschichten.

## Advanced / ML

Der 26W COT-Index und die Commercial-Range werden nicht entfernt. Sie bleiben in Advanced-Charts, Research Lab und Trade-Snapshots verfügbar, damit sie später gegen die neue 156W-State/Transition/Release-Logik getestet werden können.

## UI

Watchlist, Forex Matrix und Marktanalyse zeigen 156W-State, Transition und Release als primäre COT-Struktur. FULL/LOW HEDGE ohne bestätigten Release wird separat als Watch-Zustand behandelt.
