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
| #55 | — | Closed unmerged as duplicate of #54 |
| #56 | `0cd45a6` | Clarify Portfolio Manager waiting state |
| #57 | `bf3fb3e` | Record PR56 deployment |
| #58 | `b07ee23` | Guarded manual DEMO trading + Trade Blotter |
| #59 | `dce7b52` | Record PR58 manual DEMO deployment |
| #60 | `99e2d30` | Trading Intelligence v1 + prospective degradation safeguards |
| #61 | `2d8d2c7` | Record Trading Intelligence v1 deployment |
| #62 | `b126510` | Market-first signature research tooling |
| #63 | `539c410` | Record failed-auction event-chain research |
| #64 | `029227d` | Expose missed market opportunities in dashboard |
| #65 | `d39b7a9` | Refresh status through PR64 |
| #66 | `f021b98` | Causal Missed Opportunity Classifier v1 |
| #67 | `501c18d` | Record PR66 classifier deployment |
| #68 | `172b8f3` | Historical causal pattern stability research |
| #69 | `d9dca9c` | Economic feasibility map + dashboard |
| #70 | `c62880a` | Record PR69 deployment |
| #71 | `d4dac43` | Causal × Economic Candidate Matrix |
| #72 | `9c2c80a` | Record matrix-guided reversal replays |
| #73 | `cf05e90` | Dashboard Command Center UX |
| #74 | `b5388e4` | Causal Sequence Research v1 |
| #75 | `998ddc8` | Refresh status through PR74 |
| #76 | `3251b41` | Execution-aware sequence research |
| #77 | `17a1bbb` | BTC structural displacement sequence SHADOW |
| #78 | `92ce5c6` | Enforce SHADOW worker singleton |

PR #20 was closed as superseded after its Live Opportunity Board functionality
was incorporated by the later merged main-branch work.

## Current state

- current repository served: `92ce5c6` through PR #78; frontend Command Center UX is active, BTC structural displacement sequence is deployed SHADOW/PAPER-only, and the SHADOW worker is singleton-protected;
- economic reference capital: 400 EUR (1% = 4 EUR, 2% hard ceiling = 8 EUR, daily max 3% = 12 EUR);
- runtime: 23 SHADOW scanners = 20 baseline + GBP directional pullback + GBP Asia range sweep + BTC structural displacement sequence;
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


## PR #56 — Portfolio waiting-state truth

Status: **MERGED + DEPLOYED** at `0cd45a6`.

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


## PR #58 — manual DEMO trade dashboard + Trade Blotter

Status: **MERGED + DEPLOYED** at `b07ee23`.

Branch: `feat/manual-demo-trade-dashboard`.

Backend:

- manual DEMO preview model/service;
- manual DEMO submit with explicit confirmation;
- manual-close endpoint restricted to `TradingNew:manual_demo:*` tickets;
- same central risk engine as automatic trades;
- no manual lot override;
- no manual bypass of macro, daily-loss, spread/stop, margin or broker-demo
  guards;
- manual entry blocked while a PAPER or Trading-New bridge position is open.

Frontend:

- asset / side / SL / TP / risk form;
- live Bid/Ask reference;
- preview with calculated lot, expected loss, spread/stop, RR and margin;
- explicit browser confirmation before submit;
- Trade Blotter for broker DEMO positions and PAPER history;
- close button only on manual Trading-New positions.

Validation so far:

- 9 manual-execution tests passed;
- full backend suite: 161 tests passed;
- Ruff passed;
- frontend TypeScript/Vite build passed;
- live EURUSD preview proof passed with no MT4 command written.


## PR #60 — Trading Intelligence v1 (8-step observability/research layer)

Status: **MERGED + DEPLOYED** at `99e2d30`.

Branch: `feat/trading-intelligence-v1`.

No trading-policy change.

Backend additions:

- `/api/v1/intelligence/overview?hours=24`;
- `/api/v1/execution/demo/quality`;
- `/api/v1/qualification/history`;
- `/api/v1/reports/daily`;
- market-first opportunity capture telemetry;
- trade/probe MFE/MAE + signal-to-entry waiting metrics;
- persistent AUTO/MANUAL DEMO command/result audit;
- persistent prospective-qualification history;
- daily report writer;
- per-asset research state;
- bounded recent-MT4 CSV reader to keep intelligence snapshots cheap.

Worker behavior:

- command/result and qualification history are updated every cycle;
- intelligence + daily report are generated at most every five minutes;
- no strategy thresholds or broker guards are changed.

Dashboard:

- 24 h market-first opportunities / captured / missed;
- daily PAPER result;
- DEMO fill/refusal/slippage metrics;
- prospective qualification counts;
- research/collect state by asset;
- recent MFE/MAE/waiting-cost table;
- qualification timeline;
- explicit data limitations.

Validation checkpoint:

- targeted intelligence/audit/API tests passed;
- full backend suite: **177 passed**;
- Ruff clean;
- frontend TypeScript/Vite build clean;
- current real 24 h intelligence runtime: 113 market opportunities, 15 captured,
  98 missed after ±3 M5 signal matching;
- optimized snapshot runtime: ~0.43 s on the runtime host.


## PR #62 — Market-First Signature Research tooling

Status: **MERGED** at `b126510`.

Branch: `research/btc-missed-opportunity-signatures`.

Research-only additions:

- reusable `market_first_signatures.py` service;
- CLI `scripts/analyze_market_first_signatures.py`;
- fixed causal feature extraction over frozen train / validation / holdout;
- semantic archetype summaries across all five retained assets;
- dedicated tests.

No runtime scanner, admission, execution, sizing, risk, stop or target is changed.

Research outcome from the first pass:

- BTC generic reversal / continuation / compression signatures rejected;
- BTC failed-auction pre-stretch and 96-M5 structural-extreme significance
  hypotheses rejected;
- GBP compression and early-displacement variants rejected;
- XAU early-displacement continuation rejected;
- stable market-first signature prevalence is not sufficient evidence of edge.

Next research direction: event-chain significance rather than static-bar
patterns.


## PR #63 — failed-auction event-chain research

Status: **MERGED** at `539c410`.

Branch: `research/btc-failed-auction-displacement`.

Read-only replay only; no runtime change.

- BTC full sweep-candle displacement confirmation: rejected on validation;
- BTC pre-sweep micro-pivot confirmation: rejected on all windows;
- XAU full displacement confirmation: positive but severely under-sampled in
  train/validation and 2/2 losses in holdout;
- XAU feasibility remains constrained by the 0.01 minimum lot at 400 EUR.

No strategy is promoted from this branch.


## PR #64 — Missed Opportunity Review dashboard

Status: **MERGED + FRONTEND ACTIVE** at `029227d`.

Branch: `feat/missed-opportunity-review`.

Frontend-only intelligence improvement:

- surfaces the 12 largest `capture_state=missed` market-first episodes from the
  current 24 h snapshot;
- shows birth time, asset, future-direction label, move magnitude in ATR,
  reference price and horizon end;
- keeps an explicit warning that these are retrospective coverage episodes, not
  trading signals;
- uses the existing Trading Intelligence API; no backend/runtime decision logic
  changes.

No scanner, strategy, admission, risk, execution or bridge behavior changes.


## PR #66 — Missed Opportunity Classifier v1

Status: **MERGED + DEPLOYED** at `f021b98`.

Branch: `feat/missed-opportunity-classifier-v1`.

Trading Intelligence additions:

- causal context classification for every market-first episode;
- fixed causal classes: auction failure/reclaim, compression breakout,
  displacement, extreme/stretch, compression state, structural extreme and
  unclassified;
- causal feature payload stored with each episode;
- summary by causal pattern: total, missed, aligned, opposed, neutral and
  average future move ATR;
- dashboard pattern-summary table;
- Missed Opportunity Review now shows causal pattern and
  aligned/opposed/neutral status.

Safety:

- causal class uses only bars available at episode birth;
- future movement is used only for retrospective alignment metadata;
- no scanner, admission, sizing, stop, target, risk or bridge change;
- old Trading Intelligence cache remains backward-compatible.

Validation checkpoint:

- 183 backend tests passed;
- causal future-independence test passed;
- legacy cache compatibility test passed;
- Ruff clean;
- frontend TypeScript/Vite build clean;
- real 24 h classifier runtime remains ~0.44 s.


### PR #66 runtime proof

After merge, deployment was performed only after confirming 0 PAPER, 0
Trading-New bridge position and 0 pending command.

The first naturally refreshed post-deploy intelligence snapshot contained 112
market-first episodes and non-empty causal pattern summaries. Runtime remained
5/5 READY with 22 healthy SHADOW scans and no execution command.

The causal classifier remains research-only and does not participate in
scanner admission or broker order decisions.


## PR #68 — Historical Causal Pattern Stability report

Status: **MERGED** at `172b8f3`.

Branch: `research/causal-pattern-stability`.

Research-only additions:

- typed historical causal-pattern report models;
- reusable stability analyzer over frozen train / validation / holdout;
- CLI `scripts/analyze_causal_pattern_stability.py`;
- same market-first denominator and same causal classifier as PR #66;
- alignment rate, aligned/opposed counts and average move ATR by asset/pattern;
- dedicated tests.

First economic follow-up from the report:

- cross-asset compression-breakout anti-alignment was tested as one fixed
  false-breakout reversal mechanism;
- the mechanism failed train economics on BTC/EUR/GBP, failed all three windows
  on XAU and was fully infeasible on XAG;
- no runtime strategy is promoted.

Validation:

- 185 backend tests passed;
- Ruff clean;
- runtime trading code and dashboard are unchanged by this branch.


## PR #69 — Economic Feasibility Map

Status: **MERGED + DEPLOYED** at `d9dca9c`.

Branch: `research/economic-feasibility-map`.

Research-only additions:

- typed economic-feasibility report models;
- historical feasibility by asset, causal pattern and 0.50 / 0.75 / 1.00 /
  1.50 ATR stop widths;
- exact reuse of `size_position()` with the 400 EUR reference capital;
- spread, minimum-lot, margin and other rejection attribution;
- symbol-level feasible stop envelope and minimum theoretical capital;
- CLI `scripts/analyze_economic_feasibility.py` with optional snapshot output;
- cached `economic_feasibility_latest.json` artifact;
- read-only `/api/v1/research/economic-feasibility` endpoint;
- dashboard Economic Feasibility Map;
- dedicated tests.

Key result:

- XAGUSD has no feasible stop-distance interval at 400 EUR under the frozen
  0.07 spread, neither at 1% nor at the 2% absolute risk ceiling;
- XAUUSD is most feasible around 0.5–0.75 ATR stops;
- BTC/EUR/GBP require wider stops mainly because of spread economics.

No runtime scanner, strategy, risk or bridge behavior changes.

Validation: 191 backend tests passed; Ruff clean; frontend TypeScript/Vite build passed.


## PR #71 — Causal × Economic Candidate Matrix

Status: **MERGED** at `d4dac43`.

Branch: `research/causal-economic-candidate-matrix`.

Research-only additions:

- typed causal/economic matrix report;
- deterministic directional-consistency states;
- exact reuse of PR #68 causal split statistics;
- exact reuse of PR #69 economic sizing/stop profiles;
- CLI `scripts/analyze_causal_economic_matrix.py`;
- dedicated test.

First result:

- 35 asset/pattern cells analyzed;
- no ALIGNED_STABLE cell;
- 9 economically feasible OPPOSED_STABLE cells across BTC/EUR/GBP/XAU;
- XAG OPPOSED_STABLE cells remain unusable because the asset-level feasible stop
  interval is empty at 400 EUR.

No runtime or dashboard change in this branch.


## Research checkpoint — matrix-guided reversal replays

Branch: `research/gbp-structural-extreme-reversion`.

Read-only replay results:

- GBPUSD structural_extreme_stretch opposite-side reversal: rejected on train,
  validation and holdout;
- XAUUSD directional_displacement opposite-side reversal: rejected on train,
  validation and holdout.

No runtime change.

Decision: coarse single-state anti-alignment is insufficient. Next chantier is
Causal Sequence Research v1 using multi-M5 state transitions before market-first
moves.


## PR #73 — Dashboard Command Center UX

Status: **MERGED + FRONTEND ACTIVE** at `cf05e90`.

Frontend-only usability refactor:

- new permanent **Command Center** summary with the seven operational metrics
  needed for day-to-day supervision:
  system readiness, auto-DEMO state, Trading-New positions, PAPER PnL today,
  executable opportunities, macro gate and prospective progress;
- four explicit dashboard views:
  `Vue d’ensemble`, `Trading`, `Marchés`, `Recherche`;
- default overview reduced to command center + compact session preflight +
  Trade Blotter;
- technical preflight timeline moved behind a collapsed details control;
- trading execution/manual/portfolio/gates isolated in the Trading view;
- quotes and execution feasibility isolated in the Markets view;
- intelligence, strategy map, funnel, probes, SHADOW/PAPER and admission moved
  to the Research view;
- sticky navigation and responsive mobile layout;
- legacy nine-card summary grid retained in source but no longer displayed.

No backend, scanner, admission, sizing, risk, stop/target or broker bridge behavior
changes.

Validation: frontend TypeScript/Vite build passed; git diff check clean.


## PR #74 — Causal Sequence Research v1

Status: **MERGED** at `b5388e4`.

Research-only additions:

- typed three-M5 causal sequence report;
- causal direction from the latest non-neutral state in the sequence;
- train / validation / holdout sequence statistics;
- all-occurrence directional MFE lift versus per-asset baseline;
- all-occurrence symmetric first-touch (+1.5 ATR before -1.5 ATR) lift;
- ambiguous same-M5 double-touch exclusion;
- CLI `scripts/analyze_causal_sequences.py`;
- dedicated first-touch and sequence-direction tests.

Research result so far:

- only BTC and XAU retained a strict >50% first-touch sequence across all three
  windows with minimum sample support;
- both failed actual economic replay because train expectancy remained negative;
- no strategy is promoted.

No runtime scanner, admission, risk, execution or dashboard behavior changes in
this research branch.


## Next chantier — Execution-Aware Sequence Research

The next research step must use actual executable path geometry earlier in the
discovery process instead of applying broker economics only after a sequence has
been selected.

Planned scope:

- reuse causal three-M5 sequences from PR #74;
- label every occurrence with first-touch outcomes derived from economically
  feasible stop geometry by asset;
- keep frozen spread, minimum lot, margin, macro and 400 EUR risk policy;
- compare sequence success to the corresponding asset baseline in
  train / validation / holdout;
- replay only sequences that remain positive after this execution-aware screen;
- do not add a runtime strategy without independent positive train,
  validation and holdout evidence.


## PR #76 — Execution-Aware Sequence Research

Status: **MERGED** at `3251b41`.

Research-only additions:

- execution-aware sequence report models;
- per-asset economically preferred ATR stop geometry;
- next-M5 entry + fixed 1R screening target + 12-M5 horizon;
- exact frozen spread/slippage and existing `size_position()` reuse;
- macro/min-lot/margin/spread-stop rejection attribution;
- train / validation / holdout baseline expectancy;
- sequence expectancy delta versus asset baseline;
- strict 30 / 10 / 5 minimum executable support;
- CLI `scripts/analyze_execution_aware_sequences.py`;
- dedicated consistency tests.

Result:

- three-state screen: exactly one POSITIVE_STABLE cell,
  BTCUSD `structural_extreme -> directional_displacement ->
  directional_displacement`;
- independent screen expectancy +0.037R / +0.138R / +0.202R;
- sequential no-overlap replay remains positive at
  +0.012R / +0.138R / +0.202R on 39 / 15 / 9 trades;
- four-state extension yields zero POSITIVE_STABLE cells.

No runtime strategy is added in this branch.


## PR #77 — BTC structural displacement sequence

Status: **MERGED + DEPLOYED** at `17a1bbb`.

Single trading hypothesis:

`BTCUSD structural_extreme -> directional_displacement ->
directional_displacement`

Implementation contract:

- BTCUSD only;
- side = latest directional causal state in the three-M5 sequence;
- next-M5 entry in historical replay / current broker quote in SHADOW runtime;
- stop = 1.50 ATR M5;
- target = 1.00R;
- max holding = 12 M5;
- frozen research spread/slippage unchanged;
- runtime live spread, 400 EUR / 1% sizing, macro, min-lot and margin guards unchanged;
- LIVE remains OFF.

Official application backtest reproduces the research replay exactly:

- 139 candidates / 63 executed;
- train 39 trades, +0.0122R expectancy, PF 1.031, DD 5.046R;
- validation 15, +0.1384R, PF 1.372, DD 1.200R;
- holdout 9, +0.2015R, PF 1.605, DD 2.000R;
- official admission: SHADOW / insufficient independent evidence;
- `paper_collection_candidate=true`.

Runtime dry-run in `/tmp`:

- 23 scanners total;
- exactly one new `structural_displacement_sequence` scanner;
- symbol = BTCUSD only;
- current state at validation checkpoint = NO_SIGNAL;
- no runtime or MT4 artifact modified by the dry-run.

Temporary full admission refresh also confirms the new BTC strategy as SHADOW and
PAPER-eligible, with no ACTIVE strategy created.


## PR #78 — Shadow worker singleton hardening

Status: **MERGED + DEPLOYED** at `92ce5c6`.

Operational incident observed on 2026-09-22:

- two Trading-New `app.shadow_worker` processes were running against the same
  runtime directory;
- no PAPER trade, Trading-New broker position or pending broker command existed
  at the checkpoint;
- the orphan worker was stopped and the canonical PID metadata was repaired;
- runtime remained 5/5 READY.

Hardening:

- `app.shadow_worker` now acquires an OS-level non-blocking `flock` for the
  full worker lifetime;
- a second worker exits immediately instead of sharing the ledger/runtime;
- `ops/start_trading.sh` now waits up to 5 seconds for an unhealthy old worker
  to stop;
- if the old PID remains alive, startup aborts instead of spawning a duplicate;
- lock PID is written to `shadow/worker.lock` for operational inspection.

No strategy, admission, sizing, risk, stop/target or bridge semantics change.

Validation:

- 211 backend tests passed;
- dedicated singleton tests passed;
- Ruff clean;
- `bash -n ops/start_trading.sh` clean;
- frontend TypeScript/Vite build passed.


## 2026-09-22 — checkpoint de reprise apres PR #79

Etat reel relu avant reprise du developpement :

- #73 est deja **MERGED + FRONTEND ACTIVE** ; aucun redeploiement ni restart
  backend/worker n etait necessaire ;
- #74 a finalise le filtrage des sequences sur toutes les occurrences ;
- #76 a introduit le screening execution-aware ;
- #77 a ajoute le seul candidat survivant, BTC structural displacement
  sequence, en SHADOW/PAPER uniquement ;
- #78/#79 ont securise le singleton worker et documente son deploiement.

Nettoyage operationnel : le worktree temporaire `Trading-dashboard`, propre et
non utilise par le process frontend actif, a ete supprime.

Revalidation ciblee : 17 tests passent sur causal sequence, execution-aware et
parite structural displacement sequence.

Aucune modification de strategie ou d execution n est associee a ce checkpoint.

Recherche additionnelle du checkpoint : le croisement regime M15 + sequence M5
execution-aware (longueur 2) a ete teste sur les quatre actifs economiquement
faisables. Il ne produit aucune cellule `POSITIVE_STABLE`; aucun changement
runtime n en decoule.

Deux prototypes research-only supplementaires ont ete rejetes sans code runtime :
modele causal continu sur les features OHLC existantes, puis extension avec
impulsion de tick-volume MT4. Aucun ne generalise sur validation + holdout ;
aucune dependance ML ni regle d execution n a ete ajoutee.


## 2026-09-23 — DEMO readiness semantics + Command Center no-trade diagnosis

Backend:

- DemoExecutionGuard now exposes transport_armed, auto_collection_armed, waiting_for_qualified_trade and qualified_collectors;
- ready keeps its strict meaning: a broker DEMO order is eligible now;
- armed transport is no longer misreported as locked merely because the portfolio is waiting for a qualified PAPER signal.

Frontend:

- Command Center reports qualified / total executable opportunities over 24 h;
- new « Pourquoi aucun trade automatique ? » panel explains the current bottleneck;
- AUTO-DEMO state displays ARMÉ · ATTENTE SIGNAL while waiting;
- preflight DEMO displays ARMED instead of the misleading LOCKED;
- direct navigation to the guarded manual DEMO form is available without submitting an order automatically.

Validation in the isolated worktree: 26 targeted backend tests passed, Ruff clean, frontend TypeScript/Vite build passed.


## 2026-09-23 — XAU Asia sweep SHADOW/PAPER scope

The existing Asia session sweep/reversal mechanism is extended from GBPUSD-only runtime scope to GBPUSD + XAUUSD, without changing the mechanism itself.

Purpose: collect prospective evidence on XAU where validation/holdout historical expectancy is positive but sample size is too small for promotion. This creates no ACTIVE or LIVE authority.

Validation so far: RED scope test first, then 19 targeted tests green; /tmp dry-run produces 24 scanners with exactly one new XAU Asia sweep scanner and no production-runtime writes.

Related scope checks remain rejected: directional pullback is not extended to EUR/XAU/BTC, and EUR Asia sweep remains disabled because it has no executable validation/holdout evidence under the current broker/capital contract.


## PR #82 — XAU Asia sweep collector deployed

Status: **MERGED + DEPLOYED** at `5a2782f`.

Operational result after a worker-only restart and the first full cycle:

- 24 SHADOW scanners total;
- 24 PAPER states;
- 6 PAPER/demo-collection eligible SHADOW strategies;
- exactly one new scanner: `XAUUSD:asia_range_sweep_reversal`;
- current new scanner state = NO_SIGNAL;
- no broker order, PAPER position or LIVE authority created.

The backend/frontend processes were not restarted for this deployment. Runtime remains READY 5/5 and AUTO-DEMO remains armed while waiting for an executable qualified PAPER signal.


## 2026-09-23 — executable-but-unqualified evidence capture

Backend:

- every SHADOW scanner still uses the existing admission policy for real PAPER;
- when PAPER entry is not admitted, an executable signal can now open an isolated research probe;
- the probe uses the exact same entry/stop/target/bar-resolution model as PAPER but is stored outside the PAPER registry;
- Opportunity Funnel reports aggregate and per-strategy unqualified-probe evidence.

Frontend:

- Research / Opportunity Funnel adds `Exec. non qualifiées suivies`;
- it shows resolved/open counts, total R, expectancy and W/L;
- per-strategy executable counts display the observed unqualified-probe expectancy when available.

Validation complete: 217 backend tests pass, Ruff clean and the frontend TypeScript/Vite build passes. Isolated runtime dry-run: 24 diagnostics, 18 unqualified-probe states (none for the 6 PAPER-eligible collectors), no current signal, and zero production-runtime writes.


## 2026-09-23 — PR #84 deployed

`Track executable unqualified signals prospectively` is merged and active at `13398a3`.

Runtime result:

- backend loaded the new funnel schema;
- worker loaded the new isolated research-probe path;
- 18 non-qualified scanner states are tracked outside the PAPER registry;
- qualified collectors remain 6 and scanners remain 24;
- dashboard Research view exposes unqualified-probe counts, expectancy and W/L;
- frontend remained hot-served on port 5180 without restart.

Safety after deployment: READY 5/5, LIVE OFF, 0 PAPER open, 0 Trading-New bridge position, 0 pending open/close command. No risk, lot, cap, spread, stop/target, macro or admission threshold was changed.


## 2026-09-23 — probe qualification visibility

Opportunity Funnel now computes an all-history research qualification for executable-but-unqualified probes using the existing prospective thresholds. The public state is deliberately renamed `SUPPORTS_REVIEW` instead of `SUPPORTS_DEMO` so the research signal cannot be confused with execution authority.

Frontend Research view adds:

- number of mechanism/symbol pairs ready for dedicated review;
- per-strategy `n/20` progress and research state;
- explicit copy that review readiness does not authorize PAPER or DEMO.

No worker, scanner, signal, risk, sizing, spread, stop/target or admission behavior changes in this branch.


## 2026-09-23 — PR #86 deployed + probe-copy hardening

Probe qualification visibility from PR #86 is active. The frontend can now show `COLLECTING`, `FAILED` and `SUPPORTS_REVIEW` with resolved-sample progress while execution authority remains unchanged.

The first deployed probe is XAUUSD post-shock continuation and remains outside PAPER/DEMO.

A targeted follow-up hardens wording so research-probe states can never be mistaken for PAPER evidence: collecting reasons report `n/20 resolved executable probes`, and failed reasons are explicitly labelled `executable-probe`.


## 2026-09-23 — most-observed probe progress in Overview

Backend Opportunity Funnel adds a compact research-progress candidate selected only by largest resolved executable-probe sample, with deterministic strategy-id tie breaking.

Frontend Command Center adds a `Recherche · candidat le plus observé` card showing symbol, resolved/minimum sample, mechanism, research state and expectancy. The card is descriptive and does not rank strategies by profitability.

Validation: 219 backend tests pass, Ruff clean, targeted frontend build passes, and a read-only production calculation returns XAUUSD post-shock continuation at 1/20 / -1R / COLLECTING.


## 2026-09-23 — executable opportunity → guarded manual DEMO preview

Backend candidate:

- new `/execution/demo/manual/opportunity-preview` endpoint;
- accepts only the retained symbol + existing mechanism;
- requires the latest SHADOW diagnostic to still be `signal_executable`;
- rejects stale diagnostics (>3 minutes), stale/missing broker quotes and invalid
  current stop geometry;
- derives TP from the live broker entry, structural stop and mechanism `target_r`;
- reuses the existing manual DEMO sizing/risk/macro/position guards at base risk;
- preview is read-only and does not create a command.

Frontend candidate:

- executable rows in Live Opportunity Board expose `PRÉPARER DEMO`;
- the backend preview fills symbol, side, SL, TP and risk in the existing form;
- explicit `CONFIRMER DEMO` remains mandatory.

Validation: 23 targeted tests, 222 full backend tests, Ruff and Vite build pass.
Deployment remains blocked while the current Trading-New PAPER/broker position is open.
## 2026-09-23 — PAPER → broker fill fidelity

Execution audit candidate:

- open-command audit records the reference monetary risk;
- filled orders derive fill-based stop risk from the same reference risk model;
- each execution sample reports risk delta EUR / %, reference RR, fill RR and RR delta;
- summary reports average risk delta, maximum observed risk increase and minimum
  fill RR;
- manual and automatic DEMO orders use the same instrumentation;
- dashboard Trading Intelligence adds a fill-risk fidelity card.

No execution authority or guard changes. Validation: 26 targeted tests, 219 full
backend tests, Ruff clean and frontend Vite build clean.
## 2026-09-23 — hot runtime deployment drain

New operational safety primitive:

- atomic runtime drain state outside static process configuration;
- worker checks drain on every collection cycle;
- PAPER and broker DEMO new-entry paths honor the same drain state;
- existing trade lifecycle and close commands bypass the new-entry block so
  draining cannot strand an open Trading-New position;
- manual DEMO is also blocked while drained;
- frontend shows and controls the drain explicitly.

No strategy, admission, risk, lot, cap, spread, stop/target or LIVE rule changes.

Validation: 224 backend tests pass, Ruff clean, frontend Vite build clean.


## 2026-09-23 — P0 broker realized PnL reconciliation

New read-only broker-history reconciliation:

- starts from closed Trading-New tickets recorded by the execution audit;
- searches MT4 `mt4_history_*.json` exports by ticket and magic 560619;
- reports exact daily realized broker PnL only when every closed ticket is found;
- otherwise keeps broker realized PnL UNKNOWN and lists missing tickets;
- dashboard now shows exact realized PnL and number of reconciled Trading-New
  tickets instead of the previous permanent UNKNOWN placeholder.

Runtime dry-run on the first automatic trade: 1/1 ticket reconciled, +2.64 EUR.
Validation: 231 backend tests pass, Ruff clean and frontend Vite build passes.
## 2026-09-23 — P1 explicit probe review queue

Opportunity Funnel now returns `unqualified_probe_review_queue` for every
strategy whose prospective executable-probe evidence reaches
`SUPPORTS_REVIEW`.

The Research dashboard renders the queue with:

- strategy/mechanism;
- resolved sample / minimum sample;
- expectancy R;
- profit factor;
- max drawdown R;
- explicit `REPLAY DÉDIÉ REQUIS` action.

No automatic promotion is possible from this queue.
Validation: 228 backend tests pass, Ruff clean and Vite build passes.


## 2026-09-23 — P3 Review Pack + Trailing Manager roadmap

A read-only `review_probe_candidate.py` workflow now turns a future
`SUPPORTS_REVIEW` family into a reproducible dedicated replay pack:

- verifies that the family is actually in the prospective review queue;
- reruns exactly that symbol/mechanism on frozen train/validation/holdout;
- attaches current historical admission and split performance;
- never writes runtime admissions or changes PAPER/DEMO authority.

This is the safe bridge from prospective probe evidence to a possible future
frequency increase.

Trailing Manager is added to the roadmap as a separate exit-management
experiment. It starts replay-only and is constrained to never widen the initial
stop or increase initial monetary risk.


## 2026-09-23 — Trailing Manager v0 replay + prospective SHADOW

New research-only exit-management components:

- `TrailingManagerConfig` separates stop trailing from target extension so each
  hypothesis can be tested independently;
- causal replay consumes closed M5 bars only;
- invariant checks forbid widening the initial stop or increasing initial risk;
- paired research runner preserves the exact static entry sample;
- dedicated CLI compares static vs treatment train/validation/holdout;
- stop-only policy is rejected on expectancy;
- target-only policy improves expectancy in all three independent windows with
  unchanged drawdown, but only 10 adjustments exist historically;
- prospective SHADOW collector therefore records future counterfactual results
  without modifying PAPER or broker execution;
- `/api/v1/research/trailing-shadow` exposes read-only progress;
- Research dashboard shows resolved count, expectancy delta, improved/worsened
  count and total adjustments.

No admission, PAPER authority, DEMO order, SL, TP, risk, lot, cap, spread guard
or LIVE setting is changed by this candidate.

Validation: 241 backend tests pass, Ruff clean and frontend build passes.


## 2026-09-23 — deployed Trailing SHADOW + orphan-process-safe stop

Trailing Manager research from PR #96 is active in production runtime as
research-only collection:

- target-only candidate remains the only prospective policy under observation;
- stop-trailing hypothesis remains rejected and inactive;
- no broker/PAPER TP or SL is modified;
- first SHADOW state starts with 0 resolved future trades.

Deployment validation exposed an ops gap in `stop_trading.sh`: PID-file-only
shutdown can miss a still-running process when its PID file is absent/stale.

The stop script now safely reconciles actual processes after PID-file shutdown,
matching repo cwd + expected command before killing any orphan. It also fails
closed on unexpected port occupants and waits for confirmed process exit.

Isolated test: orphan backend listener + worker + frontend listener all stopped
on temporary ports without touching the live runtime. Full backend suite:
241 passed.


## 2026-09-23 — research-only target + protective-stop mode

Trailing Manager research now supports an incremental
`target-plus-protection` mode:

- target extension keeps the same causal trigger as TP-only;
- SL movement is disabled until the target is already extended;
- once enabled, the same no-widen / no-added-risk stop invariant applies.

Replay improved train only and produced no incremental validation/holdout
benefit. Therefore the mode is not used by the live SHADOW collector and does
not change PAPER/broker behavior.

## 2026-09-23 — PR #95–#98 consolidated status

The first end-to-end DEMO trade has moved Trading-New from transport validation
to evidence accumulation.

Delivered:

- exact broker-history PnL reconciliation;
- executable-unqualified probe review queue + dedicated replay workflow;
- hot runtime deployment drain;
- guarded manual DEMO preparation from executable signals;
- PAPER -> broker fill risk/RR fidelity;
- prospective TP-dynamic Trailing SHADOW;
- orphan-process-safe runtime stop script.

Rejected and therefore inactive:

- XAU failed-auction x USD-pressure filter;
- XAU post-shock x USD-pressure filter;
- standalone dynamic SL trailing;
- SL protection after TP extension (no incremental validation/holdout benefit).

Current auto-DEMO execution remains unchanged: six admitted SHADOW collectors,
base risk 1%, existing spread/lot/cap guards, LIVE OFF.


## 2026-09-23 — prospective causal first_seen observability

Backend candidate:

- new isolated causal precursor ledger per symbol;
- atomic prospective collection-start state;
- one observation maximum per symbol / closed M5;
- reuses the existing causal classifier instead of defining new signal
  thresholds;
- Trading Intelligence attaches earliest aligned pre-birth precursor, pattern,
  lead time and observation count to market opportunities;
- top-level precursor denominator excludes opportunities born before collection
  startup.

Worker:

- collection executes as observability only;
- precursor errors are reported independently and cannot block the main SHADOW
  scan / PAPER / bridge lifecycle.

Frontend:

- Research view shows prospective opportunities seen before birth, eligible
  denominator, coverage rate and average lead time.

No trading authority or risk geometry changes.
Validation: 245 backend tests, Ruff clean, Vite build clean.


## 2026-09-23 — deployed causal first_seen collector

The prospective causal precursor collector from PR #100 is active in production as research-only observability.

Operational behavior:

- starts from an explicit prospective timestamp;
- no historical first_seen backfill;
- one observation maximum per symbol / closed M5;
- only directional causal states already known by the existing classifier are persisted;
- market-first opportunities can now expose earliest aligned pre-birth first_seen and lead time;
- only opportunities born after collection startup enter the first_seen coverage denominator.

Deployment preserved all trading authority and risk settings. Postflight: READY 5/5, 24 scanners, 6 qualified collectors, DRAIN OFF, LIVE OFF, 0 PAPER / bridge position / pending command.


## 2026-09-23 — precursor conversion attribution

Trading Intelligence now classifies the prospective opportunity funnel into UNSEEN, PRECURSOR_ONLY, SIGNAL_BLOCKED and SIGNAL_EXECUTABLE.

New aggregate metrics separate:

- causal detection failures;
- precursor-to-signal conversion failures;
- execution blocks;
- executable capture;
- signals that appear without a persisted precursor.

The frontend first_seen card reports the conversion funnel and average causal lead time. No execution behavior changes.


## 2026-09-23 — deployed precursor conversion funnel

PR #102 is active. Future market opportunities born after prospective precursor startup will now be attributed to UNSEEN, PRECURSOR_ONLY, SIGNAL_BLOCKED or SIGNAL_EXECUTABLE.

The Research view reports precursor-to-signal conversion and lead time. This is observability only and leaves all execution/admission/risk rules unchanged.

Post-deploy: READY 5/5, DRAIN OFF, LIVE OFF, 6 qualified collectors, 0 PAPER/bridge/pending command.

## 2026-09-24 — Precursor Forward-Excursion Pack

Backend research additions:

- `PrecursorForwardResearchReport` with raw and independent no-overlap samples;
- forward 12-M5 favorable MFE / adverse MAE / signed close return for every
  prospective causal precursor;
- summaries by causal pattern and by symbol;
- read-only `/api/v1/research/precursor-forward` endpoint;
- fixed historical validation script for a selected existing causal pattern,
  with no threshold/grid search.

Frontend Research adds:

- `Précurseurs · forward 12 M5` summary card;
- compact per-pattern table with independent sample, MFE, MAE, signed close
  return, favorable dominance and close alignment.

No runtime execution behavior changes. Targeted backend tests and frontend Vite
build pass.

## 2026-09-24 — deployed precursor forward research

PR #104 is active in production as a read-only research surface.

Runtime authority is unchanged: 6 qualified collectors, base risk 1%, existing
spread/lot/cap guards, auto-DEMO armed, DRAIN OFF, LIVE OFF.

The next development track is `Precursor Conversion Discriminator`: one new
causal information source at a time, evaluated on all precursor occurrences
before any strategy implementation.

## 2026-09-24 — precursor microstructure hypotheses rejected

Prospective spread/ATR and 2-minute broker-mid velocity were tested as fixed
continuous discriminators on the no-overlap precursor sample.

Neither justified a runtime filter, scanner change or admission change.

Next research source is macro/event context, kept research-only until independent
evidence exists.

## 2026-09-24 — XAU risk-feasible Asia pullback prospective SHADOW

Research-only components added:

- `XauFeasiblePullbackState`, probe and summary models;
- prospective state/ledger isolated from PAPER and blocked-probe ledgers;
- exact 400 EUR / 1% min-lot risk-feasible limit computation;
- fixed 3-M5 fill window and original signal horizon;
- conservative stop-before-target replay;
- worker observability integration isolated by try/except;
- read-only `/api/v1/research/xau-feasible-pullback` endpoint;
- Research dashboard card showing fills, no-fills, wins/losses and expectancy.

No XAU admission, PAPER, DEMO, risk, lot, spread, stop or target policy changes.

Validation: 16 targeted tests, 256 full backend tests, Ruff clean, Vite build clean, and a real-data no-backfill /tmp dry-run.

## 2026-09-24 — deployed XAU feasible-pullback SHADOW

The XAU Asia risk-feasible pullback counterfactual is now collecting prospectively.
Initial state is zero-resolved by construction; historical counterfactual results were not imported into the runtime ledger.

Operational state after deployment: READY 5/5, 24 scanners, 6 qualified collectors, DRAIN OFF, auto-DEMO armed, LIVE OFF, 0 open Trading-New position.

## 2026-09-24 — prospective XAU M1 microbar worker

Added a Trading-New-only read-only microstructure collector for XAUUSD:

- broker quote sampling and M1 bid/ask/mid OHLC aggregation;
- freshness and timestamp deduplication;
- isolated state, JSONL ledger and heartbeat;
- separate singleton worker lifecycle in ops start/stop;
- read-only research API;
- Research dashboard status card.

The worker has zero execution or admission authority and does not alter existing M5/M15 scanners, risk, lot, spread, stop or target policy.

Validated with 16 targeted tests, 264 full backend tests, Ruff, shell syntax, Vite build and a 70-second live-quote `/tmp` dry-run.
## 2026-09-24 — Trade Readiness / « Pourquoi aucun trade ? »

Trading view adds a compact per-asset explanation built from already-fetched runtime data:

- number of qualified collectors;
- qualified signal count over 24 h;
- executable vs blocked signal count;
- dominant economic blocker (minimum lot / risk, spread / stop, macro, margin, stale data);
- market-first missed opportunities over 24 h;
- current state: EXECUTABLE, BLOQUÉ, ATTENTE SIGNAL or RESEARCH.

This is frontend-only observability. It does not change scanners, qualification, PAPER/DEMO authority or risk.

## 2026-09-24 — deployed XAU M1 microstructure collector

PR #110 is live at `8a6e99b`.

Operational result: dedicated M1 worker healthy, canonical shadow worker unchanged, drain OFF, auto-DEMO armed and book flat after deployment.

First production M1 closed successfully with 58 quote samples; the worker continued collecting with fresh broker quotes (~2.5 s age).

No strategy/risk/admission change was made.

## 2026-09-24 — broker-equity DEMO sizing

Replaced the active 400 EUR DEMO sizing base with broker account equity (balance fallback).

Changes cover position sizing, SHADOW/PAPER diagnostics, manual DEMO preview, live market-quality economics, portfolio daily-loss budget and runtime config observability.

`reference_capital_eur` in runtime views now reflects the effective broker-derived capital and exposes its source. `research_fallback_capital_eur` retains the fixed historical fallback for reproducible backtests.

No risk fraction, spread threshold, margin fraction, stop geometry, target or LIVE flag was relaxed.

## 2026-09-24 — multi-symbol DEMO execution

Removed the global Trading-New one-position bottleneck while keeping command transport serialized.

Backend and MT4 now enforce one broker position per symbol instead of one position for the whole Trading-New portfolio. Auto-collection can advance through multiple PAPER-eligible symbols, broker position state is authoritative, and automatic close ownership is matched by exact `TradingNew:<strategy_id>` comments.

Manual DEMO blocking is also per-symbol. Drain behavior and other-system isolation are preserved.

Validation: 273 backend tests, Ruff clean, Vite build clean, MQL4 compile 0 errors / 0 warnings.

## 2026-09-24 — broker-equity sizing and multi-symbol DEMO deployed

PRs #112, #113 and #114 are active in runtime.

Active DEMO sizing capital now follows MT4 equity instead of the old 400 EUR research reference. Concurrent filled positions are allowed across different retained symbols, with same-symbol stacking still refused and command transport serialized.

Deployment proof: account flat, drain ON during activation, MT4 bridge reloaded on all five charts, fresh quote/spec files confirmed, then drain OFF. LIVE remains disabled.

## 2026-09-24 — explicit research capital replay

Opportunity backtests and portfolio research now accept optional `capital_eur`. This lets research compare the historical 400 EUR baseline with broker-equity execution feasibility while preserving deterministic historical experiments.

Runtime strategy logic and admissions are unchanged. The first broker-equity matrix produced no new ACTIVE family; it primarily increased XAU/XAG executable sample size and strengthened the already-positive BTC structural displacement sequence evidence.

## 2026-09-24 — broker-equity execution-aware sequence research

Added optional `capital_eur` to economic-feasibility and execution-aware sequence research, including CLI support. This removes the obsolete 400 EUR feasibility ceiling from DEMO-equity research while preserving the old default when no override is supplied.

Discovery result: a new XAU three-state sequence (`directional_displacement -> structural_extreme -> directional_displacement`) is robust enough for a separate SHADOW/PAPER candidate PR. No runtime scanner or admission is changed in this research PR.

## 2026-09-24 — XAU symbol-specific structural sequence candidate

Extended the existing structural-displacement sequence mechanism with a symbol-specific XAU pattern while leaving the BTC contract unchanged.

Added targeted admission-refresh support (`--symbol`, `--mechanism`, `--capital-eur`, `--merge`) and merge-safe admission persistence so a single candidate can be deployed without recalculating unrelated families.

Dry-run admission merge: 31 -> 32 entries, one new XAU sequence key, zero existing-entry changes. Candidate remains SHADOW/PAPER collection only; LIVE stays locked.

## 2026-09-24 — deployed XAU DD -> structural extreme -> DD collector

PR #118 is live. Trading-New now has 25 scanners and 7 qualified PAPER/DEMO collectors.

Deployment used a targeted merge-safe admission upsert, preserving all 31 prior strategy admissions byte-equivalently and adding only the new XAU structural sequence. No backfill or retrospective trade was created.

Drain is OFF, auto-DEMO is armed, book is flat and LIVE remains disabled.

## 2026-09-24 — XAU structural persistence sequence

Added a separate XAU-only `structural_persistence_sequence` candidate for the causal chain `directional_displacement -> structural_extreme -> structural_extreme`.

The implementation preserves the exact research geometry: next-M5 entry, 1.5 ATR stop, 1R target and 12-M5 horizon. It remains SHADOW/PAPER-only.

Also hardened PAPER concurrency to one open PAPER per symbol across strategy families while preserving multi-symbol concurrency. This aligns prospective PAPER evidence with the broker's same-symbol non-stacking rule.

Validation: 286 backend tests, Ruff clean, frontend build clean; admission merge dry-run adds exactly one key (32 -> 33) without changing existing admissions.

## 2026-09-24 — capital-aware trailing research + XAU rejection

Trailing research now propagates explicit `capital_eur` through both baseline simulation and reconstructed trailing trade sizing; CLI `analyze_trailing_manager.py` accepts `--capital-eur`.

The unchanged TP-only policy was tested on both deployed XAU sequence families at current broker-equity sizing. It fails the cross-window improvement gate on both, so no trailing execution change is made.

PR #120 deployment is also recorded: 26 scanners, 8 qualified collectors, drain OFF, auto-DEMO armed, LIVE OFF.

## 2026-09-24 — XAU M1 geometry observability

Added causal 5m/15m geometry aggregation on top of the existing broker-native XAU M1 collector and surfaced it in the Research dashboard. The pack includes move, range, path efficiency, close location, spread and quote-density metrics.

Research-only: no entry filter, stop rule, target rule or execution authority is added.

The broker-equity length-4 sequence expansion was also closed after its best supported incremental XAU candidate failed direction robustness (BUY validation negative). No post-hoc SELL-only filter is introduced.

## 2026-09-24 — causal XAU M1 signal snapshots

Added idempotent causal M1 geometry snapshots for the two deployed XAU sequence families. Signal snapshots use only M1 bars fully closed by the originating M5 signal close, preventing post-signal leakage.

The M1 Research card also reports how many sequence-signal snapshots have been frozen. This is observability/research only.

PR #122 deployment is recorded: geometry API/dashboard active, drain OFF, 26 scanners, 8 collectors, LIVE OFF.

## 2026-09-24 — prospective macro signal context

Added causal macro-event context to every SHADOW diagnostic and persisted it into future PAPER trades, blocked probes and XAU M1 sequence snapshots.

Classification is fixed and research-only: `blackout`, `post_safe` (safe resume through +135 minutes) or `normal`, using high-impact USD events. Existing macro blackout execution policy is unchanged.

Added `analyze_post_macro_opportunities.py` for reproducible broker-equity historical stratification and lightweight POST_SAFE annotations in the Opportunity dashboard.

Historical result does not authorize a strategy: XAU failed auction is promising but only 6 POST_SAFE trades; BTC failed auction is negative; XAU directional transition fails holdout.

## 2026-09-24 — demote XAU break/retest + reconcile native broker closes

Revalidated XAU break/retest at current broker-equity sizing after its first prospective loss. Validation and holdout are negative, so only that family was demoted from PAPER/DEMO authority. Qualified collectors decrease 8 -> 7; all other admissions remain unchanged.

Broker realized-PnL reconciliation now recognizes Trading-New tickets closed natively by MT4 SL/TP, using filled Trading-New open-command ownership plus broker closed history. Explicit close commands remain a completeness check.

Production ticket 185357042 now reconciles to -7,374.50 EUR instead of being omitted from the daily broker PnL.

## 2026-09-24 — hard 5-lot execution ceiling

Added a global `max_lots_per_trade=5.0` guard to shared sizing plus a second DEMO-command guard. Runtime config and manual dashboard expose the ceiling. Broker-equity sizing remains active; the ceiling only lowers actual exposure when the 1% calculation would exceed 5 lots.

## 2026-09-24 — PR126 deployment and frequency screen

Deployed the hard 5-lot Trading-New ceiling end-to-end. Broker-equity sizing remains active, but shared sizing and DEMO command submission cannot exceed 5.00 lots.

Post-deployment research re-ran broker-equity length-2 sequences and a fixed contrarian directional-displacement family. Both were rejected across independent windows, so no new runtime family was added.

Current bottleneck is signal production: the seven PAPER-eligible collectors produced zero SHADOW signals in the measured 24 h window. Research focus moves to macro-attention context and market-first unseen-opportunity discovery.

## 2026-09-24 — Unseen Opportunity Radar

Extended Trading Intelligence with a prospective `unseen_patterns` summary and added a Research dashboard table showing invisible opportunity birth signatures by pattern, symbol, side, opposition rate, move ATR, 6-M5 stretch and compression.

Also closed two fixed hypotheses without runtime changes: pre-event volume/range attention conditioning and structural-extreme-stretch exhaustion reversal. Both fail Trading-New historical evidence.

## 2026-09-24 — PR128 live radar and post-deployment research

Unseen Opportunity Radar is deployed in backend + Research dashboard. Runtime remains READY 5/5, 26 scanners, 7 collectors, drain OFF, LIVE OFF and hard 5-lot ceiling active.

Two follow-up rules were rejected without runtime changes: unclassified 6-M5 momentum continuation across all five assets, and an externally motivated XAU Asia-BUY / US-SELL session rule. Neither is robust across train/validation/holdout.

## 2026-09-24 — reproducible value-of-waiting research

Added `unclassified_transition_research` plus CLI coverage for the first-directional-transition-after-unclassified hypothesis. It measures transition coverage, direction alignment, wait bars, ATR consumed, expectancy, PF and drawdown by train/validation/holdout.

Result: high directional alignment does not translate into positive execution expectancy because the M5 confirmation arrives after too much of the move has been consumed. No scanner/admission/order behavior is added.

## 2026-09-24 — persistent XAU unseen/M1 research ledger

Added a persistent, idempotent research ledger joining XAU market-first unseen/unclassified opportunities to causal M1 geometry at birth and to the first directional M5 transition within three bars. The M1 dashboard card exposes the accumulated sample count.

This collector has no order/admission authority and is intentionally prospective-only because no long historical XAU M1 dataset is available.

## 2026-09-24 — M1 research expanded to BTC/EUR/GBP/XAU/XAG

Generalized the existing broker-native M1 collector and unseen-transition ledger to all five Trading-New assets while preserving the XAU compatibility surface. Added multi-asset API/dashboard observability. One singleton worker still samples all symbols.

No trading authority changes.

## 2026-09-24 — XAU precursor compression forward shadow

Added a research-only forward execution shadow for prospective XAU `compression_breakout` precursor observations. The forward contract is frozen at next-M5 entry, 1.5 ATR stop, 1R target and 12-M5 horizon, with current macro/cost/broker-equity/5-lot policies.

The shadow deliberately starts from zero at deployment: the 8 XAU selection trades (+0.321R expectancy, PF 2.285) are not backfilled into validation. Dashboard observability shows resolved count, expectancy, PF, wins/losses and DD. No order/admission authority is added.

Rejected in the same cycle: BTC directional-transition predecessor-regime gating and GBP failed-auction London-session gating.

## 2026-09-24 — broker position count aggregation

Fixed broker account observability to aggregate unique broker tickets across all `mt4_data_*` symbol exports instead of counting positions from only the first file. This correctly reports external Freezebee positions while preserving strict ownership separation from Trading-New bridge tickets.

PR #133 deployment also recorded: XAU compression precursor forward shadow is live research-only and starts at 0 resolved observations.

## 2026-09-24 — post-PR134 checkpoint

PR #134 is deployed with backend-only restart. Broker observed-position count now correctly reports the two external Freezebee tickets while Trading-New bridge positions remain zero. XAU precursor compression forward validation is active at 0/20 with no post-start compression precursor observed yet.

## 2026-09-24 — XAU auction-failure precursor forward validation

Added a second isolated research-only precursor execution shadow for future XAU `auction_failure_reclaim` observations. It uses the same frozen next-M5 / 1.5 ATR / 1R / 12-M5 contract, current DEMO broker equity, macro/cost policies and hard 5-lot ceiling as the compression precursor shadow.

Selection screen: BTC rejected (-0.713R over 7 trades); XAU promising (+0.396R, PF 2.585, 75% wins over 8 trades) but explicitly under-sampled. Forward validation starts at zero with no backfill and has no order/admission authority.

## 2026-09-24 — reject sparse negative holdout from SHADOW PAPER collection

Changed the SHADOW paper-collection gate so a sparse but observed negative holdout can no longer be bypassed by positive train+validation. Empty holdout remains collectable; observed holdout must be >=0R.

Immediate runtime impact after targeted admission refresh: `GBPUSD:directional_pullback_resumption` will become observation-only. The change does not alter signals, stops, targets, sizing, the 5-lot ceiling or LIVE state.

Also documented the XAU break/retest loss: pre-cap 11.22-lot trade, -1R PAPER / -7374.50 EUR broker, stopped almost immediately with <0.12R favorable excursion; trailing would not have helped.


## 2026-09-25 — unseen-transition research summary API

Added a read-only multi-asset summary over the prospective `*_unseen_m1_transitions.jsonl` ledgers. The endpoint `/api/v1/research/unseen-transitions` reports per symbol:
- total episodes and resolved/unresolved counts;
- aligned versus opposed first directional transitions;
- alignment rate over resolved episodes only;
- median M5 bars waited;
- median ATR consumed overall and on aligned transitions.

This turns the PR #131/#132 prospective M1 evidence into a stable comparison surface without introducing thresholds or a trading rule.

PR #137 postflight was also rechecked: the negative-holdout GBP directional-pullback family is no longer PAPER/DEMO eligible. Existing PR #48 positive-independent-window semantics remain unchanged.

Validation: 314 full backend tests pass, Ruff clean, diff check clean.


## 2026-09-25 — prospective M1 directional quote-pressure features

Extended the existing multi-asset prospective M1 collector with backward-compatible microstructure fields:
- `mid_up_ticks` and `mid_down_ticks` on each M1 bar;
- `directional_tick_samples` and `mid_tick_imbalance` on 5/15 minute geometry;
- `spread_change` over the same causal window.

The imbalance is deliberately named as a mid-price tick proxy, not OFI. The current MT4 feed has quote prices but no Level-2 size/depth, so the system must not claim order-book imbalance.

The change is motivated by the current frequency bottleneck: eligible strategies produced no signals after the 2026-09-24 XAU trade while several observation-only mechanisms remained active. New microstructure fields are collected only for future evidence and are not wired into execution.

Validation: 314 backend tests pass, Ruff clean, diff check clean.


## 2026-09-25 — PR #139 deployed

Merged and deployed the prospective M1 directional tick-imbalance instrumentation as PR #139 (`26d9591`).

Runtime postflight:
- backend and M1 worker restarted under drain;
- shadow worker was not restarted;
- drain returned OFF;
- five markets healthy;
- Trading-New book and bridge flat;
- no pending demo command;
- 5-lot ceiling and broker-equity sizing unchanged.

New up/down tick counts are being populated prospectively on BTCUSD, EURUSD, GBPUSD, XAUUSD and XAGUSD. Geometry-level imbalance intentionally waits for newly closed M1 bars; there is no synthetic backfill.


## 2026-09-25 — unseen tick-pressure research summary

Added a prospective-only aggregation layer over unseen M1 opportunity births:
- exclude legacy episodes that have no real directional tick samples;
- convert M1 tick imbalance to opportunity-side-aligned pressure;
- separate resolved aligned vs opposed transitions;
- expose median 5m/15m pressure and directional tick sample counts.

Also refreshed the shadow worker under drain after detecting it had remained on the pre-PR #139 in-memory code. This ensures future unseen snapshots carry the newly collected M1 microstructure fields.

No execution logic consumes these metrics.


## 2026-09-25 — blocked probe outcomes by guard reason

Extended the opportunity funnel so resolved blocked-probe outcomes are attributed to their exact `block_reason`.

Each reason now reports:
- tracked / resolved / open probes;
- wins / losses;
- total R;
- expectancy R.

This prevents spread rejects and minimum-lot/risk-granularity rejects from being conflated in research analysis.

Current evidence supports keeping the spread guard unchanged: 150 resolved spread-blocked probes are -49.55R in aggregate with -0.33R expectancy; even the marginal 0.15-0.20 spread/stop band is negative.


## 2026-09-25 — deployment backlog checkpoint

Confirmed there is no pending software deployment:
- `main == origin/main == 5ddbe2c`;
- PR #139 through #142 are merged;
- no open PR remains;
- runtime is READY 5/5 with drain OFF and auto-collection armed.

Current waiting time is prospective-evidence collection, not an undeployed release. The project deliberately keeps the 20-observation research-review floor, the 15% spread/stop guard and the 5-lot ceiling unchanged while new evidence accumulates.


## 2026-09-25 — positive prospective candidate progress surface

Extended the opportunity funnel with positive_unqualified_candidates.

The new read-only surface reports current positive executable-probe candidates with wins/losses, total R, expectancy/PF/DD, remaining observations to the fixed 20-trade review floor and sample progress.

This avoids conflating “most observed” with “most promising” while preserving the existing prospective qualification contract. No auto-promotion or trading rule is added.

Validation: 9 focused tests and 318 full backend tests pass; Ruff and diff checks clean.


## 2026-09-25 — prospective edge progress dashboard

Improved research observability while prospective samples accumulate.

The positive candidate surface is now visible on the dashboard with sample progress toward 20/20, W/L, total R, expectancy, PF and DD. The overview card also prefers a currently-positive prospective candidate over the merely most-observed family.

Fixed an associated consistency issue: candidate W/L and total R now use the same lifetime prospective probe sample as qualification, rather than the shorter funnel display window.

No scanner, admission, order, risk, stop, target, spread, macro or lot-cap behavior changes.


## 2026-09-25 — faster MT4 live quote readiness path

Replaced full-history M5 loading inside live quote sparkline construction with the existing recent-bar loader capped at 48 bars.

Observed cold quote-read latency dropped from roughly 7.5 s to 0.36 s, with warm reads around 0.01 s. This directly reduces /session/preflight and market-universe latency without changing trading logic or quote semantics.

Validation: 9 focused tests and 319 full backend tests pass; Ruff and diff checks clean.


## 2026-09-25 — market-first Value of Waiting surface

Added causal first-system-reaction timing to market-first opportunity episodes and a new waiting_costs aggregation by strategy.

The Research dashboard now shows how much of each later market move was already consumed when SHADOW first reacted, how much remained, and whether a prospective precursor existed before the signal.

Pre-birth signals are treated as early reactions and count as 0 ATR consumed. The future move remains retrospective research metadata only and cannot authorize an order.

Validation: 18 focused tests, 320 full backend tests, Ruff clean and frontend production build clean.


## 2026-09-25 — isolate 168 h Value of Waiting refresh

The Research dashboard now refreshes Value of Waiting on its own 168 h / five-minute cadence while retaining the existing 24 h core intelligence refresh.

This keeps the operational dashboard responsive and gives the waiting-cost analysis enough observations to be meaningful. Failed 168 h refreshes retain the last valid snapshot.

No execution, admission or risk behavior changes. Frontend production build passes.


## 2026-09-25 — join M1 pressure and precursor context to Value of Waiting

Added optional early-context enrichment to the 168 h Trading Intelligence research view.

The enrichment joins each first SHADOW reaction to only the M1 microbars fully closed before that reaction, side-adjusts 5m/15m quote-direction imbalance, and detects a same-side precursor inside the existing 15-minute capture window. It separates M1 coverage from actual directional tick-pressure coverage so legacy/zero-directional-sample bars are never interpreted as neutral pressure.

The dashboard now exposes collection counters and compares the requested 25-40% consumed diagnostic cohort against reactions below 25% when both samples become available. No threshold, admission, spread, sizing, stop, target, macro or 5-lot rule is changed.

Current evidence is collection-only: 71 waiting episodes, 6 with M1 coverage, 5 historical episodes in the 25-40% cohort, and 0 target-cohort episodes with prospective M1 coverage so far.

Validation: 20 focused tests, 322 full backend tests, Ruff clean and frontend production build clean.


## 2026-09-25 — probe winner/loser early-context comparison

Added a research-only outcome discriminator for resolved prospective unqualified probes.

The report joins each probe to causal M1 pressure and same-side precursor context available before its signal, then separates tick-pressure winners from losses by strategy. It exposes coverage, W/L, total R, expectancy, winner/loser 5m and 15m imbalance medians, and precursor rates.

Current post-collector evidence is deliberately small but already rejects a naive rule: 4 probes have genuine tick-pressure, all 4 lost, despite mildly positive side-aligned 5m imbalance and precursor presence. Therefore neither positive quote-direction pressure nor pressure+precursor is treated as a standalone early-entry signal.

No scanner, admission, spread, sizing, stop, target, macro or 5-lot rule changes.

Validation: 21 focused tests and 323 full backend tests pass; Ruff and frontend production build are clean.
