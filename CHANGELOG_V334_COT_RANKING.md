# V3.3.4 · Minimal COT Ranking

## Ziel

Die Watchlist wurde auf eine einfache, transparente Ranking-Ansicht reduziert.

## Ranking

Die Haupttabelle enthält nur Märkte, deren aktueller 26W
Commercial COT-Index in einer Extremzone liegt.

### Rang 1 · 3/3

Bullish:
- COT >= 80
- Commercial-Netto-Perzentil >= 80
- Retail-Netto-Perzentil <= 20

Bearish:
- COT <= 20
- Commercial-Netto-Perzentil <= 20
- Retail-Netto-Perzentil >= 80

### Rang 2 · 2/3

COT-Extrem plus genau eine der beiden Netto-Bestätigungen.

### Rang 3 · 1/3

Aktuell nur das COT-Extrem.

Es gibt keinen gewichteten Score. Innerhalb eines Rangs erfolgt lediglich
alphabetische Sortierung.

## Bewusst nicht im Ranking

- Commercial Range
- Velocity
- Spekulativer Flow
- Divergenz
- Saisonalität

Diese Informationen bleiben in der Marktanalyse verfügbar.

Aktive Releases werden separat dargestellt, weil der aktuelle COT-Index nach
einem Release bereits außerhalb der Extremzone liegt.

## Unverändert

Die Analyse-, CFTC-, Preis-, NC-Divergenz-, Research- und Config-Logik wurde
nicht verändert.
