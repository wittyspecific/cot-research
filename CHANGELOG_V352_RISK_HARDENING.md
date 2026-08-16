# V3.5.2 · FTMO Risk Engine Hardening

## Ziel

V3.5.2 härtet die bestehende read-only FTMO/MT5 Portfolio-&-Risk-Engine gegen Konzentrationsrisiken ab. Die COT-, Seasonality- und Research-Logik bleibt unverändert; es werden weiterhin keine Orders gesendet oder bestehende Positionen verändert.

## Konservative interne Standard-Policy

Die offiziellen FTMO-2-Step-Grenzen bleiben unverändert bei 5 % Maximum Daily Loss und 10 % Maximum Loss. Die folgenden Werte sind ausschließlich interne Sicherheitslimits:

- Zielrisiko je Trade: 0,25 %
- Max. Einzeltrade: 0,50 %
- Max. Instrument / Idee: 0,50 %
- Max. Open Stop Risk: 2,00 %
- Max. Cluster Risk: 0,75 %
- Max. gerichteter FX-Faktor: 0,75 %
- Daily Safety Reserve: 2,00 %
- Max-Loss Safety Reserve: 4,00 %
- Weekend-/Gap-Stress: 2,0× bekannter Stop-Risk

## Instrument Risk

Mehrere Tickets desselben Underlyings werden zu einer gemeinsamen Risikoidee aggregiert. Broker-Suffixe wie `.cash` oder `.c` werden für diese Aggregation normalisiert. Ein zusätzlicher Trade desselben Instruments kann nicht mehr pro Ticket erneut das volle Einzeltrade-Risiko erhalten.

## Cluster-Fixes

- AUDJPY und andere valide 6-stellige FX-Paare werden zuerst als FX erkannt und können nicht mehr durch breite Index-Texttreffer falsch klassifiziert werden.
- XCUUSD/Copper wird dem Metals-Cluster zugeordnet.
- Cluster-Tabelle zeigt zusätzlich die Anzahl unterschiedlicher Instrumente neben der Anzahl offener Tickets.

## FX Currency Factor

Die FX-Faktoransicht trennt nun:

- gerichtetes Netto-Faktor-Risiko je Währung,
- Brutto-Faktor-Risiko,
- Anzahl der Tickets und betroffenen Symbole,
- internes gerichtetes Faktor-Limit und Restbudget.

Ein neuer FX-Trade wird auf Base- und Quote-Faktor geprüft. Gegenläufige Trades dürfen bestehendes gerichtetes Faktor-Risiko reduzieren; gleichgerichtete Trades werden reduziert oder blockiert, wenn ein Währungsfaktor ausgeschöpft ist.

## Portfolio Risk Status

Neue Risk-Desk-Ampel:

- GREEN: interne Limits eingehalten,
- YELLOW: mindestens ein internes Budget ist zu mindestens 75 % ausgelastet,
- RED: internes Portfolio-, Instrument-, Cluster- oder FX-Faktor-Limit verletzt, Stop fehlt oder ein interner Safety-Floor wird unterschritten.

Die Ampel ist eine interne Portfolio-Policy und keine zusätzliche FTMO-Regel.

## Pre-Trade Approval

`APPROVED / REDUCED / BLOCKED` berücksichtigt jetzt parallel:

- gewünschtes Trade-Risiko,
- Max. Einzeltrade,
- bereits vorhandenes Risiko im gleichen Instrument,
- gesamtes Open Stop Risk,
- Cluster Risk,
- gerichtete FX-Faktor-Risiken,
- Daily Safety Reserve,
- Max-Loss Safety Reserve.

Die Lotgröße wird weiterhin ausschließlich aus MT5 Tick Size, Tick Value, Entry, Stop und freigegebenem Risikobudget berechnet und auf den zulässigen Volume-Step abgerundet.

## Regression

- neue Tests für AUDJPY/XCUUSD-Klassifizierung,
- Instrument-Aggregation mehrerer Tickets,
- Instrument-Limit beim Pre-Trade Approval,
- gerichtetes FX-Netto-Risiko und Faktor-Offset,
- Portfolio-Risk-Ampel.
