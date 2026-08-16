# V3.3.9 · Full 51-Market Universe

15 neue CFTC-Märkte:
OJ, VIX, ZT, ZF, ZN, ZB, UB, KE, MWE, ZR, LBR, BRL, ZAR, BZ, RS.

Gesamtuniversum: 51 Märkte.

Resolver:
- exakte CFTC Contract Market Codes haben höchste Priorität
- Brent darf gezielt `LAST DAY` enthalten
- übrige Exclusion-Regeln bleiben erhalten

Routing:
- Rates / Volatility -> TFF
- Commodities / Forest Products -> Disaggregated
- Legacy bleibt für die Watchlist erhalten

Preis:
- HRSpring und Canola ohne erzwungenen unbestätigten Yahoo-Ticker
- VIX nutzt ^VIX als Preisproxy

Keine Änderung an Produktionsschwellen oder Analyseformeln.
