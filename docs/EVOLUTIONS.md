# Evolutions and PR tracking

Last updated: 2026-09-21.

## Merged evolution history

| PR | Commit | Evolution |
|---|---|---|
| #1 | `da3d367` | Bootstrap Python/FastAPI + React M5/M15 platform |
| #2 | `d2e2cb3` | MT4 market selector and 200 EUR capital risk engine |
| #3 | `28127ae` | Regime-first replay and REJECTED/SHADOW/ACTIVE admission |
| #4 | `69ad0d1` | Causal opportunity engine and MT4-aware backtester |
| #5 | `0386eba` | Prospective BTC SHADOW scanner and control panel |
| #6 | `c14718d` | Live MT4 market board with broker prices |
| #7 | `3ea7699` | Live dashboard M5 freshness fix |
| #8 | `ee45283` | Prospective SHADOW paper lifecycle |
| #9 | `be90345` | Multi-market portfolio core, qualification and cost telemetry |
| #10 | `a338b67` | DEMO execution guards, macro gate and resilient operations |
| #11 | `e91e4d7` | Separation of SHADOW research PnL from portfolio risk |
| #12 | `d6cccad` | Read-only multi-market MT4 quote bridge |
| #13 | `1366a23` | Paper entry-bar causality fix |
| #14 | `d9cfb7d` | Directional transition SHADOW mechanism |
| #15 | `44efa28` | Session preflight and self-healing worker |
| #16 | `e315ad2` | Node 22 frontend autostart fix |
| #17 | `1c3d6ea` | Session reopen M5-gap warmup guard |
| #18 | `8a418d0` | Preflight waits for fresh M5 resynchronization |
| #19 | `01dd91a` | Session timeline and stalled-M5 detection |
| #21 | `1b52231` | Live multi-market opportunity board + explicit paper admission gate |
| #23 | `731ecdf` | Blocked-opportunity prospective probes |
| #24 | `c1dcb7d` | Capital feasibility for blocked opportunities |
| #25 | `71b4bd4` | Live capital/execution feasibility matrix |
| #26 | `634d2b4` | Historical/runtime macro policy parity |
| #27 | `910da36` | Legacy vs post-cutover paper evidence separation |
| #28 | `7e8893f` | Project status, evolutions and five-asset scope |
| #29 | `347e1b8` | GBP directional pullback resumption SHADOW |
| #30 | `d138a3a` | MT4 exporter locked to five active markets |
| #31 | `1d4552a` | Paper entries focused on positive historical SHADOW evidence |
| #34 | `5ca52a9` | Frozen reproducible research execution costs |
| #36 | `14427e5` | PAPER collection for promising under-sampled SHADOWs |
| #37 | `fcf5c50` | Refresh deployed status through PR #36 |
| #38 | `587cae7` | GBP Asia range sweep SHADOW/PAPER candidate |

PR #20 was closed as superseded after its Live Opportunity Board functionality
was incorporated by the later merged main-branch work.

## Current state

- PR #29 is merged and deployed: GBPUSD `directional_pullback_resumption`, SHADOW-only;
- current deployed main: `587cae7`;
- runtime: 22 SHADOW scanners = 20 baseline + GBP directional pullback + GBP Asia range sweep;
- current Portfolio Manager: `NO_TRADE`;
- first clean post-cutover paper result: GBP failed-auction **+1.5R / +2.7329 EUR**;
- DEMO bridge: locked;
- live trading: locked;
- post-cutover prospective evidence: 1 closed GBP failed-auction trade,
  +1.5R / +2.7329 EUR.

## Scope decision — 2026-09-21

Development is intentionally limited to:

`BTCUSD, EURUSD, GBPUSD, XAUUSD, XAGUSD`

Explicitly abandoned from the active program:

`US500Cash, USA500IDXUSD, USATECHIDXUSD, Volatility, VOLIDXUSD`

This is a scope reduction, not an exporter-data investigation backlog. Do not
reintroduce these symbols unless the project scope is explicitly changed later.

## Next PR policy

The next trading PR should contain one measurable trading hypothesis for the
five retained assets, with:

- causal signal definition;
- unchanged risk policy;
- train / validation / holdout evidence;
- execution feasibility under 200 EUR;
- SHADOW-only activation first;
- no DEMO activation unless both historical and prospective contracts pass.


## PR #29 — directional pullback resumption

Status: **MERGED + DEPLOYED / SHADOW-only**.

Scope:

- new mechanism `directional_pullback_resumption`;
- runtime collection restricted to GBPUSD;
- unchanged risk, macro and spread/stop policies;
- runtime collection is GBPUSD-only;
- frozen-cost evidence after PR #34:
  - train 9 trades, +0.197R;
  - validation 8 trades, +0.438R;
  - holdout 1 trade, -0.240R;
- admission remains SHADOW and cannot authorize DEMO.


## PR #30 — five-market exporter scope

Status: **MERGED + DEPLOYED**.

- MT4 exporter defaults restricted to BTCUSD, EURUSD, GBPUSD, XAUUSD, XAGUSD;
- abandoned index/volatility aliases removed from source;
- backend and exporter scope locked by automated tests;
- no trading/risk behavior change.


## PR #31 — positive-SHADOW paper focus

Status: **MERGED + DEPLOYED**.

- all SHADOW scanners continue to run;
- blocked probes and diagnostics remain unchanged;
- new PAPER entries require either ACTIVE admission or SHADOW admission with
  positive weakest independent expectancy;
- historically negative SHADOW mechanisms no longer start fresh paper trades;
- existing open paper trades are allowed to finish normally;
- risk, lot, stop, target and broker execution guards are unchanged.


## PR #34 — reproducible research execution costs

Status: **MERGED + DEPLOYED**.

- historical admission spread is being frozen per active symbol from observed
  median broker spreads;
- runtime execution continues to use live Bid/Ask;
- purpose: prevent admission results from changing with refresh time-of-day;
- GBP directional-pullback evidence is corrected: under the frozen median cost
  model its holdout is 1 trade at -0.240R, so it remains observation-only.


## Promising SHADOW PAPER collection

Deployed in PR #36:

- keep REJECTED admissions fully blocked;
- ACTIVE admissions remain PAPER-eligible;
- SHADOW admissions remain eligible when weakest independent expectancy is
  positive;
- additionally allow PAPER collection when train and validation expectancy are
  both positive even if an under-sampled holdout is currently negative;
- this affects research PAPER only and cannot authorize DEMO.

With the frozen matrix, this newly adds only
`GBPUSD:directional_pullback_resumption`; XAU failed-auction was already
eligible under the positive-weakest rule.


## PR #36 — promising SHADOW PAPER collection

Status: **MERGED + DEPLOYED / PAPER research policy**.

- REJECTED admissions remain fully blocked;
- ACTIVE admissions remain PAPER-eligible;
- positive-weakest SHADOW admissions remain PAPER-eligible;
- a SHADOW with positive train + positive validation may collect PAPER even if a
  tiny holdout is currently negative;
- frozen-matrix impact: exactly two PAPER-eligible pairs:
  - GBPUSD:directional_pullback_resumption;
  - XAUUSD:failed_auction_reversal;
- no DEMO admission or risk policy change.


## PR #38 — GBP Asia range sweep

Status: **MERGED + DEPLOYED / SHADOW + PAPER collection**.

- new mechanism `asia_range_sweep_reversal`;
- shared causal geometry for historical replay and runtime scanning;
- runtime scope restricted to GBPUSD;
- registry slug: `asia_range_sweep`;
- frozen-cost replay reproduced: train 19 / +0.078R / PF 1.15, validation
  2 / +1.017R / PF 99, holdout 0;
- historical admission remains SHADOW;
- `paper_collection_candidate=true` under the existing train+validation-positive
  collection rule;
- no DEMO authority, risk, lot, spread, macro or capital-policy change.


## In-flight — five-asset runtime hardening + dashboard truth

Branch: `fix/runtime-five-asset-watchdog`.

- constrain runtime quote/universe discovery to the five active markets;
- eliminate the >15s abandoned-symbol universe scan observed after PR #38;
- make `session_state.json` atomic under concurrent preflight calls;
- close the startup lock FD before spawning backend, worker and frontend so the
  watchdog can self-heal again;
- prevent overlapping frontend refresh cycles;
- expose admission thresholds and `paper_collection_candidate` truth in the
  dashboard;
- add a ROAD TO BROKER DEMO panel with market readiness, scanner count, PAPER
  candidates, prospective progress and remaining execution locks.

Validation: 125 backend tests passed before the dashboard additions; targeted
runtime reads on real MT4 files returned the five active symbols in about
0.02 seconds. No risk or trading admission threshold is relaxed by this PR.
