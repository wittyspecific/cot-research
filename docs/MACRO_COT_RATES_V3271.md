# V3.27.1 · Treasury Duration COT

## Ziel

Der Macro × COT Regime Layer erhält einen eigenen Treasury-Duration-Block.

2Y, 5Y, 10Y und 30Y Treasury COT werden **nicht** als vier unabhängige
Cross-Asset-Stimmen gezählt. Zuerst entsteht ein einzelnes Rates-Regime,
das anschließend genau einmal in Cross-Asset Breadth und Transition Pressure
eingeht.

## Rates State

Mögliche Zustände:

- BROAD DURATION ACCUMULATION
- BULLISH DURATION
- BULLISH DURATION LEAN
- MIXED DURATION
- BEARISH DURATION LEAN
- BEARISH DURATION
- BROAD DURATION DISTRIBUTION
- INSUFFICIENT DATA

## Methodik

Die Treasury-Tenors verwenden den bereits bestehenden strukturellen COT-State.

Bei TFF ist das der Asset-Manager-Block. Dealer/Intermediary wird weiterhin
nicht als physischer Commercial Hedger interpretiert.

Broad Duration Accumulation verlangt:

- breite bullish Positionierung über mehrere Treasury-Tenors,
- 2W-Breadth,
- 4W-Breadth,
- ausreichende Persistenz,
- und bei der stärksten Klassifikation überwiegend aktiven Positionsaufbau
  statt bloßem Short-Unwinding.

Die internen Tenor-Gewichte und der Cross-Asset-Basket-Weight stehen zentral in
`config/macro_cot_regime.toml`.

## Cross-Asset Integration

Das synthetische Treasury-Duration-Regime zählt genau einmal.

Beispiel:

Macro: Late Expansion / Deteriorating
Equities: Risk-Off
JPY / CHF: Defensive
Treasuries: Broad Duration Accumulation, 2W/4W persistent

→ Late Expansion Warning / Peak Watch wird stärker bestätigt.

Der Rates-Block erzeugt weiterhin keinen Entry.
