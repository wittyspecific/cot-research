
# V3.24.0 · Makro Model Library — Macro Navigation Rebuild

## Design

The Macro Model Library is a regime layer, not an entry engine.

Hierarchy:

1. Business Cycle Core
2. Phase-conditional Imminent Recession Cluster
3. Model Breadth / Scatter as diagnostics
4. Liquidity as modifier
5. Existing Macro-COT / Seasonality / COT dynamics / price structure
6. Existing execution and risk management

The implementation is inspired by public business-cycle concepts described in
Henrik Zeberg's 2026 working paper, but it does **not** claim to reproduce the
proprietary Zeberg Business Cycle Model. Exact weights, transformations,
smoothing and equilibrium construction are not public.

## Public Equilibrium Proxy

Each feature is transformed in its native release frequency first.

Examples:
- PAYEMS: MoM and rolling 3M payroll changes on monthly observations.
- UNRATE: 3M / 6M changes on monthly observations.
- ICSA: 4W / 13W changes on weekly observations.
- PERMIT / HOUST / INDPRO: monthly 3M and YoY changes.
- Daily rate/market series are reduced to weekly observations before macro transforms.

Features are standardized with a prior-only robust rolling reference. The
composite tier index is then compared with a prior-only long-term rolling median.
This is the project's transparent equilibrium proxy.

## Four Cycle Phases

- EXPANSION
- SLOWDOWN
- CONTRACTION
- RECOVERY

`LATE_SLOWDOWN` is a transition state, not a fifth primary cycle phase.

## Imminent Recession

The cluster is gated by a confirmed SLOWDOWN. Signals can be observed outside
Slowdown but do not become active cluster votes.

Current criteria:
- rapid short-term-yield decline
- re-steepening after prior inversion
- claims deterioration
- labor deterioration
- credit deterioration
- coincident rollover

## Breadth

Atomic models and family consensus are explanatory diagnostics.

A 70% family breadth threshold can label broad agreement, but breadth never
overrides the Business Cycle Core. Leading/Coincident disagreement can be
expected sequencing.

## Liquidity

Three channels:
- policy liquidity
- credit liquidity
- market liquidity

Liquidity can be SUPPORTIVE / NEUTRAL / RESTRICTIVE. It changes interpretation
of timing, amplitude and persistence only.

## Point in Time

The current provider stores `observation_date` and a conservative
`availability_date`. Transformations are computed in native frequency and
aligned only after availability.

However, FRED graph CSV history is revised history. True historical backtests
still require ALFRED or another vintage source.
