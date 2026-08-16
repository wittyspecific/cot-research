# V3.4.0 · Forex COT Matrix + 20Y/40D Seasonality

Neue separate Forex-Seite.

## COT Relative Strength
11 COT-Währungen -> 55 eindeutige Crosses.

Currency Strength:
- bullish 3/3 = +3
- bullish 2/3 = +2
- bullish 1/3 = +1
- neutral = 0
- bearish 1/3 = -1
- bearish 2/3 = -2
- bearish 3/3 = -3

Pair Bias:
`base_strength - quote_strength`

## Pair Seasonality
Für jedes konkrete Währungspaar:
- Historie: 20 abgeschlossene Jahre
- Horizont: nächste 40 Handelstage
- Anker: gleicher Trading-Day des Jahres
- mindestens 8 historische Jahresbeobachtungen

Richtung:
- bullish, wenn Median > 0 und positive Quote > Pair-Basisrate
- bearish, wenn Median < 0 und positive Quote < Pair-Basisrate
- sonst gemischt

Die Seasonality wird nicht in den COT-Paarbias eingerechnet.
