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
