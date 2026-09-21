# Project status — 2026-09-21

## Objective

Build a causal M5/M15 trading system that can progress from research to SHADOW,
then DEMO, without increasing risk to compensate for missing edge.

Economic reference capital remains **200 EUR**.

## Active market scope

Development and runtime scope is now intentionally restricted to:

- BTCUSD
- EURUSD
- GBPUSD
- XAUUSD
- XAGUSD

The following symbols are explicitly out of scope and must not be added to the
watchlist or used to justify faster activation:

- US500Cash
- USA500IDXUSD
- USATECHIDXUSD
- Volatility
- VOLIDXUSD

## Deployed runtime

Current deployed main commit: `fcf5c50` (PR #37).

Operational services:

- frontend: port 5180
- backend: port 8020
- SHADOW worker: self-healing heartbeat/watchdog
- 21 active SHADOW scanners: 5 markets × 4 baseline mechanisms + 1 GBPUSD-only directional pullback
- PAPER entries are limited to ACTIVE, positive-weakest SHADOW, or SHADOW with positive train + validation evidence
- MT4 DEMO bridge: present but locked
- live trading: locked

Latest runtime checkpoint after PR #36 deployment:

- Portfolio Manager: **NO_TRADE**;
- first clean post-cutover paper trade closed:
  `GBPUSD:failed_auction_reversal`, BUY, target hit, **+1.5R / +2.7329 EUR**;
- no post-cutover paper position is currently open;
- MT4 DEMO bridge: 0 bridge positions, 0 pending commands, still locked.

No strategy currently satisfies both:

1. historical admission = ACTIVE;
2. prospective post-cutover paper qualification = SUPPORTS_DEMO.

## Risk policy

- reference capital: 200 EUR
- base risk: 1% / trade
- absolute max: 2% / trade
- daily max loss: 3%
- spread / stop ceiling: 15%
- max margin fraction: 25%

Risk, lot size and caps must not be raised to repair negative expectancy.

## Evidence integrity

### Macro parity

PR #26 aligns historical replay with the same HIGH-impact USD macro blackout
used by runtime. On the frozen 5 × 4 matrix, 168 historical candidates were
inside macro blackout windows. No strategy became ACTIVE after correction.

### Paper causality cutover

PR #13 fixed paper entry-bar causality.

The evidence cutover is:

`2026-09-20T12:53:56+03:00`

PR #27 keeps all earlier trades for audit but excludes them from prospective
qualification metrics.

Current ledger separation at the checkpoint:

- post-cutover: 1 closed GBPUSD trade / +1.5R / +2.7329 EUR;
- legacy pre-cutover: 7 BTC trades / -7R / -10.8621 EUR.

The legacy losses remain visible and are never deleted.

## Current market constraints

Live capital/execution feasibility has shown:

- BTCUSD: currently the clearest market compatible with 200 EUR under the
  existing risk policy;
- EURUSD / GBPUSD: lot granularity is compatible; spread can still block
  narrow-stop setups, but GBPUSD has now produced the first executable
  post-cutover paper entry;
- XAUUSD / XAGUSD: many setups are structurally blocked by minimum-lot
  granularity at 200 EUR.

Blocked opportunities are followed prospectively instead of weakening the risk
policy.

## Research already rejected

Do not reopen these tests without a materially different hypothesis:

- London opening-range breakout;
- generic balance -> expansion trigger;
- BTC US-session-only filter;
- BTC failed-auction structural significance score tested on the existing
  features;
- BTC spread/stop relaxation from 15% to 16%;
- spread/stop tightening from 15% to 12%.

None produced robust train + validation + holdout evidence.

## Known data limitation

MT4 HST v401 files expose a spread field, but IronFX stores it as zero across the
available BTC/EUR/GBP/XAU/XAG M5 histories. Therefore historical replay cannot
recover true historical spread from the local HST files.

Historical research now uses a frozen, versioned observed-median spread proxy
plus modeled slippage. Runtime decisions still use the live broker spread.

This improves reproducibility but remains a proxy, not tick-accurate historical
execution reconstruction.

## Immediate development priority

Focus only on BTC/EUR/GBP/XAU/XAG.

The next work should increase the probability of finding executable edge, not
add infrastructure:

1. collect `directional_pullback_resumption` prospectively on GBPUSD only;
2. continue the existing five-market/four-mechanism SHADOW collection;
3. keep BTC as the primary broadly executable market and continue post-cutover
   prospective evidence;
4. keep XAU/XAG in observation/blocked-probe mode until a genuinely structural
   setup fits the 200 EUR capital policy;
5. preserve macro, spread, capital and causality gates;
6. move SHADOW -> DEMO only after historical ACTIVE + prospective SUPPORTS_DEMO.


## Prospective PAPER focus

The SHADOW state can mean either promising but under-sampled evidence or simply
insufficient sample despite negative independent expectancy. To avoid spending
prospective paper capacity on already-negative evidence, new paper entries are
restricted to:

- ACTIVE admissions; or
- SHADOW admissions with `weakest_expectancy_r > 0`.

PR #36 adds a deliberately narrow exception to the positive-weakest rule: a
SHADOW may collect PAPER when **train expectancy > 0 and validation expectancy
> 0**, even if a still-small holdout is negative. This is research collection
only; the historical admission remains SHADOW and DEMO remains locked.

All scanners and blocked-probe ledgers continue to collect regardless.

After freezing research costs, `GBPUSD:directional_pullback_resumption` has:

- train: positive expectancy;
- validation: positive expectancy;
- holdout: 1 trade at -0.240R.

It remains historical SHADOW and cannot authorize DEMO. It is the sole new
candidate for accelerated PAPER collection under the train+validation-positive
rule.

The only positive weakest-expectancy SHADOW in the current frozen matrix is
`XAUUSD:failed_auction_reversal`, based on only four executable historical
trades and frequently blocked by minimum-lot capital granularity.

Existing paper trades are not force-closed by this policy.


## Deployed PAPER eligibility after PR #36

The frozen admission registry currently exposes exactly two PAPER-eligible
couples:

- `GBPUSD:directional_pullback_resumption` — eligible because train and
  validation are positive while the holdout is only one trade;
- `XAUUSD:failed_auction_reversal` — eligible because weakest independent
  expectancy is positive, though live execution is often blocked by minimum-lot
  capital granularity.

No additional BTCUSD or EURUSD mechanism became PAPER-eligible.


## Candidate in development — GBP Asia range sweep

Branch: `feature/gbp-asia-range-sweep`.

A distinct GBPUSD session-reversal mechanism is being promoted from fixed
research into prospective collection as `asia_range_sweep_reversal`:

- Asia range: 02:00 <= M5 open < 10:00, Europe/Athens;
- London observation: 10:00 <= M5 open < 13:00;
- first qualifying sweep of the completed session range only;
- sweep magnitude > 0.10 ATR M5;
- reclaim at least 0.02 ATR back inside the range;
- rejection wick >= 35% and coherent close location;
- entry on the next M5;
- stop beyond the sweep extreme by 0.15 ATR;
- target 1.5R, horizon 12 M5;
- unchanged macro, 200 EUR capital, 1% base risk and 15% spread/stop gates.

Frozen-cost GBPUSD replay reproduces the original research exactly:

- 85 candidates, 21 executable;
- train: 19 trades, +0.078R expectancy, PF 1.15;
- validation: 2 trades, +1.017R expectancy, PF 99;
- holdout: 0 trades.

Decision: historical state remains **SHADOW**. Because train and validation are
both positive, `paper_collection_candidate=true` under the PR #36 policy.
Runtime collection is GBPUSD-only. This mechanism cannot authorize DEMO.
