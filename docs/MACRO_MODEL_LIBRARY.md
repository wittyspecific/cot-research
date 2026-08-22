# V3.23.0 · Makro Model Library

## Zweck

Die Makro Model Library ist ein Research-/Regime-Layer. Sie erzeugt keine
eigenständigen Entries und verändert in V1 weder Watchlist noch COT-,
Seasonality-, Risk- oder Execution-Core.

Hierarchie:

1. Makro Model Library
2. Macro COT Regime
3. Seasonality Turning Windows
4. COT Positioning Dynamics
5. Markt-/Trendstruktur
6. Entry / Execution / Position Sizing

## Datenregister V1

| Key | Provider | Series-ID | Frequenz | konservativer Known-at Lag | Transformation |
|---|---|---:|---|---:|---|
| US 2Y | FRED | DGS2 | daily | 1d | Level, 4/13/26W change, z-score |
| US 10Y | FRED | DGS10 | daily | 1d | curve spreads, change |
| US 3M | FRED | DGS3MO | daily | 1d | curve spreads |
| Fed Funds | FRED | DFF | daily | 1d | level, Fed Funds minus US2Y |
| Unemployment | FRED | UNRATE | monthly | 40d | 3M/6M change |
| Initial Claims | FRED | ICSA | weekly | 5d | 4W/13W change |
| Continuing Claims | FRED | CCSA | weekly | 12d | 13W change |
| Nonfarm Payrolls | FRED | PAYEMS | monthly | 40d | change/momentum |
| Industrial Production | FRED | INDPRO | monthly | 50d | YoY/3M/6M |
| Building Permits | FRED | PERMIT | monthly | 50d | YoY/3M/6M |
| Housing Starts | FRED | HOUST | monthly | 50d | YoY/3M/6M |
| Manufacturing New Orders | FRED | AMTMNO | monthly | 65d | YoY/3M/6M |
| High Yield OAS | FRED | BAMLH0A0HYM2 | daily | 1d | level/4W/13W |
| Financial Conditions | FRED | NFCI | weekly | 5d | level/4W/13W |

ISM Manufacturing PMI and ISM New Orders are explicit optional slots in V1.
No unverified or fabricated FRED series is substituted. AMTMNO is used
transparently as the public manufacturing-orders proxy until a stable ISM
provider is configured.

## Point-in-Time

The FRED graph CSV endpoint returns current/revised history and does not encode
the vintage that was known on each historical date. V1 therefore stores an
`availability_date` based on conservative release lags and aligns all mixed
frequency data only backward from that known-at date.

This prevents obvious observation-label look-ahead, but it is not a substitute
for ALFRED vintages. A future provider can populate `release_timestamp` and
replace revised values without changing the model API or cache schema.

## Persistence

Macro observations are cached separately in:

`.cache/macro_model_library/macro.sqlite3`

The trading journal database is not reused. This avoids coupling macro research
data to immutable trade-plan/outcome storage. Page caching is six hours and the
provider cache TTL defaults to twelve hours.

## Score axis

Component scores use one common direction:

- `+100`: strongly supportive / expansionary
- `0`: neutral
- `-100`: strongly deteriorating / contractionary

`recession_transition_score` is separate and runs from `0` to `100` risk.

## V1 open points

- true ALFRED/vintage backtesting
- stable ISM PMI / ISM New Orders provider
- longer licensed High-Yield OAS history if FRED depth is insufficient
- model-by-model walk-forward calibration and threshold validation
- cross-asset confirmation research
- production integration into Watchlist/Signal Engine only after validation
