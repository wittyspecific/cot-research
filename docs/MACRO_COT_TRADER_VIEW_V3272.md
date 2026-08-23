# V3.27.2 · Macro × COT Trader View

## Ziel

V3.27.2 verändert nicht die Business-Cycle- oder COT-Grundarchitektur.

Der Patch behebt zwei konkrete methodische Probleme und verschlankt die
Macro × COT Regime-Seite für Trader.

## 1. Treasury COT Resolver

Treasury-Tenors werden weiterhin zuerst über `CLASSIC_MARKETS` aufgelöst.

Falls dort kein geeigneter Markt existiert, wird jetzt zusätzlich direkt das
bereits geladene CFTC-Report-Universe nach den konfigurierten Treasury-Aliases
durchsucht.

Es wird niemals ein CFTC Contract Market Code erfunden. Ein Treffer ist nur
gültig, wenn ein echter Code im Report-Universe vorhanden ist.

Zielkontrakte:

- 2Y Treasury Note
- 5Y Treasury Note
- 10Y Treasury Note
- U.S. Treasury Bond / 30Y

Damit soll der bisherige Zustand `0/4 Treasury tenors` behoben werden, sofern
die CFTC-TFF-Daten im Universe verfügbar sind.

## 2. Richtungsspezifische Persistenz

Die bisherige allgemeine COT-Persistenz konnte hoch sein, obwohl nur die
Gegenrichtung persistent war.

Neu:

- `risk_off_persistence`
- `risk_on_persistence`

Die Transition-Confirmation verwendet ausschließlich die Persistenz der
tatsächlich gesuchten nächsten Regime-Richtung.

Beispiel:

CONTRACTION → gesuchter nächster Turn = RISK-ON

Dann darf hohe Risk-Off-Persistenz nicht mehr als
`2W/4W Risk-On-COT CONFIRMED` erscheinen.

## 3. Schlankere Trader-UI

Prominent sichtbar bleiben nur:

- Economy
- Positioning
- Combined Regime
- Next-Regime Pressure
- Trader Read / Focus / Avoid
- kompakter Transition Path
- fünf gruppierte Alignment-Blöcke
- Risk-On / Risk-Off Breadth + richtungsspezifische Persistenz
- Treasury Duration State
- die wichtigsten Transition-Trigger

Alle ausführlichen Macro-, COT-, Rates- und Raw-Diagnostics liegen in einem
einzigen eingeklappten `Details & Diagnostics`-Bereich.

## Kein Entry

Die Seite erzeugt weiterhin keine BUY-/SELL-Signale.

Technical Setup und Risk Management bleiben nachgelagerte Layer.
