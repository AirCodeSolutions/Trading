# Evolutions and PR tracking

Last updated: 2026-09-22.

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
| #40 | `c314a9a` | Five-asset runtime hardening and DEMO readiness |
| #41 | `0cef8eb` | Isolated broker DEMO collection transport |
| #42 | `aa4b7f2` | Multi-instance DEMO bridge symbol routing and lock |
| #43 | `7764ec7` | Symbol-scoped broker quote/spec snapshots from each DEMO bridge |
| #44 | `eb3578b` | No-trade runtime status + dashboard state clarity |
| #45 | `fd00652` | Read-only opportunity funnel telemetry |
| #46 | `7dd72bd` | Economic reference capital 400 EUR + capital-aware funnel |
| #47 | `f9be5e4` | Record deployed 400 EUR runtime state |
| #48 | `130ef7e` | Align PAPER admission semantics and refresh 400 EUR admissions |
| #49 | `f00da09` | Refresh deployed 400 EUR admission/runtime documentation |
| #50 | `0ccdf3e` | Automatic-execution clarity + per-asset strategy map |
| #51 | `6bc4db7` | Record PR50 deployment + reject Asia midpoint variant |
| #52 | `6a7e8e6` | Collect every PAPER-eligible SHADOW strategy in isolated DEMO |
| #53 | `c487190` | Record PR52 deployment |
| #54 | `d758112` | Use freshest closed runtime bar source |

PR #20 was closed as superseded after its Live Opportunity Board functionality
was incorporated by the later merged main-branch work.

## Current state

- current deployed main: `d758112` through PR #54;
- economic reference capital: 400 EUR (1% = 4 EUR, 2% hard ceiling = 8 EUR, daily max 3% = 12 EUR);
- runtime: 22 SHADOW scanners = 20 baseline + GBP directional pullback + GBP Asia range sweep;
- 5/5 retained symbols have live quotes, M5/M15 data and broker specs;
- current Portfolio Manager: `NO_TRADE`;
- first clean post-cutover paper result remains GBP failed-auction **+1.5R / +2.7329 EUR**;
- DEMO transport: technically proven on five symbol-scoped bridge instances and **RE-ARMED** on 2026-09-22 after confirming 0 PAPER open, 0 Trading-New position and 0 pending command;
- current flags: DEMO mode, DEMO collection ON, DEMO bridge ON, live trading OFF;
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
- execution feasibility under the current 400 EUR economic reference capital;
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


## PR #40 — five-asset runtime hardening + dashboard truth

Status: **MERGED + DEPLOYED** at `c314a9a`.

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

Validation after deployment: 126 backend tests, Ruff and frontend build passed;
targeted runtime reads on real MT4 files returned the five active symbols in
about 0.02 seconds. No risk or trading admission threshold was relaxed.


## PR #41 — isolated broker DEMO collection

Status: **MERGED + DEPLOYED** at `0cef8eb`.

- new portfolio action `DEMO_COLLECTION` only for an open PAPER trade whose
  historical admission has `paper_collection_candidate=true`;
- external MT4 positions no longer block collection because the bridge owns and
  exports only MagicNumber `560619` positions;
- still allow only one Trading-New bridge position at a time until aggregate
  multi-position exposure is modeled explicitly;
- worker auto-executor mirrors the selected PAPER trade once and persists its
  lifecycle across restarts;
- explicit MT4 close command added so STOP/TARGET/TIMEOUT PAPER resolution can
  never leave a broker DEMO position unmanaged;
- bridge validates DEMO account, MagicNumber and authorized entry geometry;
- dashboard reports auto-collection state, bridge ticket, pending open/close and
  separates Trading-New positions from external broker positions;
- live trading remains disabled.

Validation before merge: 133 backend tests passed, Ruff passed, frontend
build passed and MetaEditor compiled `TradingDemoExecutionBridge.mq4` with
0 errors / 0 warnings.

Runtime activation remained locked after discovering that MT4 was running one
bridge instance per active symbol. A single shared command file meant multiple
instances could race to consume the same command.

## PR #42 — multi-instance DEMO bridge hardening

Status: **MERGED** at `aa4b7f2`; runtime DEMO activation remains locked until the upgraded bridge snapshots are verified on all five symbols.

- route open commands strictly to the chart whose `Symbol()` matches the command;
- include the symbol in explicit close commands and verify the selected ticket
  also belongs to that chart symbol;
- serialize command handling with an exclusive MT4 file lock so duplicate
  instances of the same symbol cannot execute the same command concurrently;
- keep the global MagicNumber `560619`, one Trading-New position maximum and
  all existing DEMO/risk guards unchanged;
- runtime DEMO flags stay OFF until the upgraded EA is proven active.

Validation: 134 backend tests passed, Ruff passed and MetaEditor compiled the
hardened bridge with 0 errors / 0 warnings.


## PR #43 — symbol-scoped DEMO broker snapshots

Status: **MERGED + DEPLOYED** at `7764ec7`.

Runtime verification after PR #42 showed BTCUSD/XAUUSD/XAGUSD READY but EURUSD
and GBPUSD lacked current broker Bid/Ask/spec snapshots even though their M5/M15
histories were fresh. To avoid adding another MT4 EA, each already-attached
`TradingDemoExecutionBridge` now exports its own
`trading_demo_spec_<SYMBOL>.csv` file.

- one file per chart symbol, so there is no multi-instance write contention;
- backend live quotes consume the newest scoped snapshot alongside legacy JSON;
- broker specs consume scoped snapshots without overwriting account/position JSON;
- existing `mt4_data_*` files remain untouched;
- DEMO collection and bridge flags remain OFF until runtime proof is complete;
- live trading remains disabled.

Validation before PR: 14 targeted tests passed, Ruff passed and MetaEditor
compiled the bridge with 0 errors / 0 warnings.


## 2026-09-22 — no-trade development mode and opportunity diagnosis

Runtime execution was deliberately returned to PAPER-only before analysis:

- `TRADING_EXECUTION_MODE=paper`;
- `TRADING_DEMO_COLLECTION_ENABLED=false`;
- `TRADING_DEMO_EXECUTION_BRIDGE_ENABLED=false`;
- `TRADING_LIVE_TRADING_ENABLED=false`;
- zero Trading-New broker positions and zero pending bridge commands.

Morning SHADOW evidence shows the engine is detecting opportunities, but economics
prevent execution rather than a dead scanner:

- BTCUSD examples are narrowly above the 1% base-risk budget at minimum lot;
- XAGUSD is frequently rejected by spread/stop economics;
- XAUUSD can generate positive counterfactuals but minimum-lot stop loss can
  exceed the absolute 2% cap on 200 EUR;
- the candidate GBP mechanisms did not trigger an executable signal in the
  observed morning window.

Next implementation: read-only opportunity funnel / blocked-opportunity outcome
telemetry. No trading threshold or risk policy change is part of that work.


## In-flight — PR #45 opportunity funnel telemetry

Branch: `feat/opportunity-funnel`.

Read-only engineering change. It does not alter signal geometry, sizing, risk,
admission or broker execution.

- new `/api/v1/shadow/opportunity-funnel?hours=24` endpoint;
- counts blocked vs executable SHADOW signal rows over a rolling window;
- aggregates closed and open blocked-opportunity probes;
- exposes counterfactual wins/losses, total R and expectancy;
- exposes minimum-lot capital requirements and dominant block reasons per strategy;
- dashboard adds a 24 h opportunity funnel before the detailed probe table.

Runtime data sampled during development over the trailing 24 h: 62 signal rows,
61 blocked, 1 executable; 51 blocked probes tracked, 46 resolved; blocked-probe
total -7.92R and expectancy -0.17R. The aggregate evidence argues against
blindly relaxing guards: the purpose of this telemetry is to isolate mechanisms
where economic feasibility and edge coexist.

Targeted validation: 3 new tests passed, Ruff passed, frontend build passed.


## PR #46 — capital 400 EUR + capital-aware funnel

Status: **MERGED + DEPLOYED** at `7dd72bd`.

The economic reference capital was increased by the user from 200 EUR to
**400 EUR**. This is treated as a capital-base update, not a percentage-risk
relaxation.

Unchanged policy:

- base risk = 1% per trade = 4 EUR at 400 EUR capital;
- absolute max = 2% = 8 EUR hard ceiling;
- daily loss max = 3% = 12 EUR;
- spread/stop ceiling = 15%;
- max margin fraction = 25%;
- DEMO collection OFF, DEMO bridge OFF, LIVE OFF during development.

The opportunity funnel now recomputes capital feasibility against the **current**
reference capital instead of trusting a historical boolean stored when probes
were created under 200 EUR.

Trailing-24h checkpoint at 400 EUR:

- 19 probes were blocked specifically by minimum-lot risk;
- 11/19 would now fit the 1% base-risk budget;
- those 11 resolved probes total **-1.11R**, expectancy **-0.10R**;
- 17/19 fit below the 2% hard ceiling, but 2% remains a ceiling and is not used
  as a target sizing rule;
- XAUUSD failed-auction 1%-feasible subset: +0.5R across 2 resolved probes;
- XAUUSD post-shock 1%-feasible subset: +1.8R across 1 resolved probe;
- BTCUSD directional-transition 1%-feasible subset: -1.41R across 6 resolved;
- BTCUSD failed-auction 1%-feasible subset: -2.0R across 2 resolved.

Conclusion: increasing capital improves execution feasibility but does not
justify enabling all newly feasible setups. Edge selection remains necessary.


### Runtime proof after PR #46 deployment

- 22 SHADOW scanners completed a full cycle;
- 5/5 retained symbols PAPER-ready;
- worker error = null;
- 0 PAPER position open;
- 0 Trading-New bridge position;
- 0 pending open/close/result command;
- frontend HTTP 200;
- execution remains PAPER-only, DEMO collection OFF, DEMO bridge OFF, LIVE OFF.


## PR #48 — PAPER admission semantics after 400 EUR replay

Status: **MERGED + DEPLOYED** at `130ef7e`.

The controlled 200/400 frozen-matrix comparison exposed a semantic inconsistency:
a strategy could be historically REJECTED while retaining
`paper_collection_candidate=true`. Runtime entry safety already rejected such
strategies, but the registry and dashboard could display a contradictory state.

PR #48:

- defines the special `paper_collection_candidate` flag only for SHADOW;
- REJECTED and ACTIVE decisions store that special flag as false;
- centralizes `paper_entry_allowed()` so collector and portfolio UI share one
  policy implementation;
- exposes historical weakest expectancy and actual PAPER-entry eligibility in
  the portfolio overview;
- dashboard shows `PAPER ELIGIBLE` from the real runtime decision, not from the
  special train+validation flag.

The 400 EUR admission refresh has now been applied to the 22 runtime scanners:

- PAPER eligible: BTCUSD break/retest, GBPUSD Asia sweep,
  GBPUSD directional pullback, XAUUSD break/retest;
- PAPER ineligible / REJECTED: XAUUSD failed auction;
- ACTIVE strategies: none.

The runtime registry was regenerated after merge. No broker execution flag was
changed: PAPER mode remains enabled for evidence collection while DEMO and LIVE
remain OFF.

## PR #50 — automatic-execution clarity + per-asset strategy map

Status: **MERGED + DEPLOYED** at `0ccdf3e`.

Branch: `feat/dashboard-auto-execution-map`.

Frontend-only execution clarity plus documentation/architecture updates:

- prominent `AUTO TRADING` state: PAPER-only / DEMO armed / LIVE;
- explicit five-step DEMO-order path based on the real runtime contract;
- separates PAPER eligibility from `paper_collection_candidate` DEMO collection;
- per-asset strategy map generated from the live admission registry;
- no activation button is added, so the UI cannot silently enable broker orders;
- architecture records `symbol × mechanism` as the admission unit;
- documentation records rejected fixed-hypothesis tests rather than reopening
  them later.

No risk, signal, stop, target, admission threshold or execution flag is changed.


## PR #52 — collect all PAPER-eligible SHADOW in DEMO

Status: **MERGED + DEPLOYED** at `6a7e8e6`.

Branch: `feat/demo-collect-all-paper-eligible`.

Objective: remove a transport-only bottleneck without changing strategy edge or
risk. Before this change, isolated broker DEMO collection required the special
`paper_collection_candidate` flag, which only represents the train+validation
under-sampled exception. That excluded BTCUSD `break_retest_reaccel` even
though the centralized admission policy already marks it `paper_entry_allowed`.

New contract:

- PAPER entry policy is unchanged;
- REJECTED remains forbidden;
- ACTIVE keeps its existing `DEMO_ELIGIBLE` path after SUPPORTS_DEMO;
- any SHADOW that is actually `paper_entry_allowed` may enter isolated
  `DEMO_COLLECTION` when a PAPER trade is open;
- the broker DEMO command still mirrors the exact PAPER side, lot, SL and TP;
- all macro, daily-loss, bridge-isolation and execution guards remain unchanged;
- LIVE remains OFF.

This adds BTCUSD break/retest to the DEMO-collectable set while preserving the
existing GBPUSD Asia sweep, GBPUSD directional pullback and XAUUSD break/retest
collectors.

Targeted validation before PR: 17 admission/portfolio tests passed; frontend
build passed.


## PR #54 — freshest runtime bar source

Status: **MERGED + DEPLOYED** at `d758112`.

Branch: `fix/runtime-freshest-bar-source`.

A live-runtime defect was found after PR #52: BTCUSD and XAGUSD moved to
preflight `M5_STALLED` even though broker quotes were live and their
`SYMBOL-M5.csv` files contained fresh closed bars.

Root cause:

- `mt4_live_quotes` returned the first valid source and therefore preferred a
  stale `mt4_bars_<SYMBOL>_M5.json` snapshot over a fresher live CSV;
- `load_closed_market_bars` also preferred the snapshot, and when no snapshot
  existed its fallback resolver preferred frozen research CSVs over live legacy
  CSVs.

This could make both the preflight and the SHADOW scanner use older bars while
fresh market data was already present on disk.

PR #54 centralizes runtime bar-source selection:

1. load available closed-bar snapshot, live legacy CSV and research CSV;
2. causally remove bars not closed at `evaluated_at`;
3. select the source whose latest closed bar timestamp is newest;
4. use source priority only as a tie-breaker;
5. cache parsed CSVs by mtime.

The research/backtest history resolver remains unchanged and reproducible.

Targeted RED/GREEN tests: 10 passed. Direct runtime-file proof before deployment
showed all five retained symbols on the same current M5 close instead of
BTC/XAG lagging by multiple bars.


## In-flight — Portfolio waiting-state truth

Branch: `feat/portfolio-waiting-reason`.

No trading decision changes. The Portfolio Manager now distinguishes:

- a collectable SHADOW PAPER trade that is open -> `DEMO_COLLECTION`;
- no open PAPER but one or more PAPER-eligible SHADOW strategies waiting for a
  signal -> `NO_TRADE` with an explicit waiting reason;
- no broker-evaluable admission at all -> the generic no-admission reason.

This removes the obsolete ACTIVE/SUPPORTS_DEMO-only explanation from the
current DEMO-collection workflow.

Research recorded with this change:

- three EURUSD specialist hypotheses rejected;
- BTCUSD break/retest 0.80 M15-ATR stop-floor variant rejected;
- PR #55 closed as duplicate of merged/deployed PR #54.
