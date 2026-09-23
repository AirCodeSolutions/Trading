# Project status — 2026-09-22

## Objective

Build a causal M5/M15 trading system that can progress from research to SHADOW,
then DEMO, without increasing risk to compensate for missing edge.

Economic reference capital is now **400 EUR** (updated 2026-09-22). Risk percentages remain unchanged.

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

Current repository served: `92ce5c6` (PR #78). The frontend Command Center UX is active, execution-aware sequence research is merged, the BTC structural displacement sequence is deployed as SHADOW/PAPER-only evidence collection, and the SHADOW worker is singleton-protected. LIVE remains locked.

Operational services:

- frontend: port 5180
- backend: port 8020
- SHADOW worker: 23 active scanners
- 23 active SHADOW scanners: 5 markets × 4 baseline mechanisms + GBPUSD directional pullback + GBPUSD Asia range sweep + BTCUSD structural displacement sequence
- 5/5 retained markets are PAPER-ready with live MT4 quote, M5/M15 data and broker specs
- PAPER entries remain evidence-gated; broker capital/risk feasibility is still enforced
- MT4 DEMO transport was runtime-proven across five symbol-scoped bridge instances
- **current execution state (2026-09-22): DEMO collection ARMED on the broker DEMO account; LIVE remains locked**
- live trading: locked

Latest runtime checkpoint:

- Portfolio Manager: **NO_TRADE**;
- first clean post-cutover paper trade closed:
  `GBPUSD:failed_auction_reversal`, BUY, target hit, **+1.5R / +2.7329 EUR**;
- no post-cutover paper position is currently open;
- MT4 DEMO bridge: 0 bridge positions, 0 pending commands;
- DEMO transport proof: five symbol-scoped bridge snapshots refresh correctly and a fake-symbol routing probe was not consumed by any bridge;
- current runtime flags: `execution_mode=demo`, `demo_collection=true`, `demo_execution_bridge=true`, `live_trading=false`;
- latest checked state: 23 scanners, 5/5 READY, 0 worker error, 0 PAPER open, 0 Trading-New command/position; DEMO guard waits only for a portfolio-selected collectable PAPER trade.

No strategy currently satisfies both:

1. historical admission = ACTIVE;
2. prospective post-cutover paper qualification = SUPPORTS_DEMO.

## Risk policy

- reference capital: 400 EUR
- base risk: 1% / trade = 4 EUR budget
- absolute max: 2% / trade = 8 EUR hard ceiling
- daily max loss: 3% = 12 EUR
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

- the economic reference capital is now 400 EUR, so the 1% base-risk budget is
  4 EUR and the 2% hard ceiling is 8 EUR;
- BTCUSD becomes much less constrained by minimum-lot granularity, but recent
  blocked-probe outcomes remain negative for directional-transition and
  failed-auction samples; more capital does not create edge;
- EURUSD / GBPUSD lot granularity is generally compatible; spread can still
  block narrow-stop setups independently of capital;
- XAUUSD now has some 1%-feasible probes at 400 EUR, including positive
  failed-auction and post-shock examples in the recent sample, while other XAU
  setups still exceed the base budget;
- XAGUSD remains dominated by spread/stop economics; the capital increase does
  not solve that constraint.

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
   setup fits the current 400 EUR capital policy and still shows positive edge;
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


## Current PAPER eligibility after the 400 EUR refresh

The admission registry was regenerated under the 400 EUR economic contract on
2026-09-22 after PR #48 aligned PAPER admission semantics. The current runtime
decision exposes four PAPER-eligible SHADOW strategies:

- `BTCUSD:break_retest_reaccel` — eligible because weakest independent
  expectancy is positive, despite negative train expectancy;
- `GBPUSD:directional_pullback_resumption` — eligible through the
  train+validation-positive under-sampled collection rule;
- `GBPUSD:asia_range_sweep_reversal` — eligible through the same
  train+validation-positive under-sampled collection rule;
- `XAUUSD:break_retest_reaccel` — eligible for prospective collection because
  train and validation are positive while holdout remains very small.

`XAUUSD:failed_auction_reversal` is now **REJECTED** at 400 EUR because the
larger executable sample reveals negative holdout expectancy. It is no longer
PAPER eligible. No strategy is ACTIVE.


## Deployed candidate — GBP Asia range sweep

Merged in PR #38, deployed at `587cae7`.

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


## Runtime hardening and path to broker DEMO

A deployment check after PR #38 exposed two operational defects unrelated to
strategy economics:

- `/market/mt4/universe` still discovered abandoned historical symbols and could
  spend more than 15 seconds parsing markets outside the five-asset scope;
- `ops/start_trading.sh` children inherited the startup lock, preventing the
  watchdog from restarting backend/worker after a controlled stop;
- concurrent session-preflight requests shared one `.tmp` file and could raise
  `FileNotFoundError`.

Branch `fix/runtime-five-asset-watchdog` fixes all three and adds dashboard
readiness telemetry. On real MT4 files the scoped live quote/universe reads are
about 0.02 seconds and return exactly BTCUSD, EURUSD, GBPUSD, XAUUSD and XAGUSD.

Current evidence path to broker DEMO is now explicit:

1. historical admission policy requires 40 validation trades and 20 holdout
   trades for `ACTIVE`;
2. prospective qualification requires 20 post-cutover PAPER trades, positive
   expectancy, PF >= 1.05 and max DD <= 12R;
3. current promising SHADOWs are under-sampled historically, so the fixed
   historical split cannot promote them to ACTIVE by simply waiting for more
   prospective PAPER observations.

This is a policy deadlock, not a risk problem. The next admission-policy change
should allow a `paper_collection_candidate` SHADOW to become DEMO-eligible only
after it independently satisfies the full prospective 20-trade qualification.
Risk, spread/stop, macro, margin and live-trading locks remain unchanged.


## Broker DEMO collection implementation — 2026-09-21

PR #41 is merged and deployed at `0cef8eb`. It implements the six-step path
from PAPER to isolated broker DEMO collection without changing any economic risk
limit.

The intended runtime contract is:

- a SHADOW strategy must already have `paper_collection_candidate=true`;
- a real executable PAPER trade must be open before any DEMO entry can exist;
- the exact PAPER lot, stop and target are mirrored to MT4;
- one MagicNumber `560619` position maximum for Trading-New while aggregate
  multi-position exposure is not yet modeled;
- positions from other MT4 systems are observed but never selected, modified or
  closed by this bridge;
- an idempotent worker state prevents re-sending the same PAPER trade;
- explicit close commands handle PAPER STOP/TARGET/TIMEOUT resolution;
- broker account must report DEMO and the EA independently refuses non-DEMO
  accounts;
- live trading remains disabled.

Validation on the development branch: 133 backend tests, Ruff, frontend build
and MetaEditor compilation are green; the EA compiles with 0 errors / 0 warnings.
The dashboard now exposes the collection lifecycle and Magic-scoped position
count separately from unrelated broker positions.


## MT4 multi-instance bridge hardening — 2026-09-21

Runtime inspection after attaching `TradingDemoExecutionBridge` to the five
active symbols found one instance on BTCUSD, XAGUSD, XAUUSD, EURUSD and GBPUSD.
The backend was immediately returned to PAPER with DEMO collection/bridge flags
OFF before any order was sent.

This exposed a transport race in the first bridge version: all instances shared
the same open/close command files and any instance could consume a command for a
different symbol.

PR #42 (`aa4b7f2`) hardens this contract:

- an open command is processed only when its symbol exactly matches `Symbol()`;
- close commands now carry an explicit symbol;
- the selected close ticket must also belong to the current chart symbol;
- all command handling is serialized by an exclusive MT4 lock file;
- the one-position Trading-New cap and MagicNumber `560619` remain global;
- external broker positions remain untouched;
- live trading remains disabled.

The runtime market files for BTCUSD/XAUUSD/XAGUSD continued to refresh while the
DEMO bridge was locked, so no market-data regression was observed from this
change. Full validation: 134 backend tests, Ruff and MetaEditor 0 errors /
0 warnings.


## Five-symbol broker snapshot completion — 2026-09-21

Post-merge runtime checks of PR #42 kept DEMO safely OFF and found a separate
market-readiness gap: EURUSD and GBPUSD had fresh M5/M15 history but no current
broker quote/spec snapshot, so the preflight exposed only BTCUSD/XAUUSD/XAGUSD as
READY.

Branch `fix/demo-bridge-symbol-specs` makes the existing five bridge instances
self-contained for broker metadata. Each bridge writes a unique
`trading_demo_spec_<SYMBOL>.csv` with current Bid/Ask and MT4 lot/tick/margin
specification. The backend reads these files as an additional quote/spec source
without altering legacy `mt4_data_*` account or position files.

The intended delivery condition is 5/5 READY, zero Trading-New bridge positions,
no pending open/close command, live trading disabled, then DEMO_COLLECTION may be
re-armed. Validation before PR: 14 targeted tests, Ruff and MetaEditor 0/0.


## No-trade diagnostic checkpoint — 2026-09-22

Execution is intentionally disarmed while development continues. The worker remains
healthy and scans 22 mechanisms across the five retained markets.

Observed since midnight Europe/Athens through the morning checkpoint:

- 15 signal rows were emitted by the SHADOW scanners;
- no Trading-New broker order or PAPER position is open;
- XAGUSD signals are predominantly blocked because live spread consumes too much
  of the structural stop distance;
- BTCUSD directional-transition / failed-auction examples were only marginally
  above the 1% base-risk budget at the broker minimum lot (~2.18–2.19 EUR stop
  loss versus a 2 EUR base-risk budget on 200 EUR);
- XAUUSD produced economically interesting blocked probes, including a
  failed-auction +1.5R counterfactual, but its 0.01 minimum lot would have risked
  ~6.16 EUR at the structural stop, above the 4 EUR absolute cap;
- no risk limit is relaxed to convert these blocked opportunities into trades.

The next engineering step is a read-only opportunity funnel: detected signal →
economic block reason → counterfactual outcome. This must expose where
opportunities are lost without changing strategy thresholds, lots or risk.


## Opportunity funnel implementation — PR #45 deployed

The no-trade diagnosis is now encoded as read-only runtime telemetry rather than
a manual log inspection. The funnel measures a rolling window of SHADOW signal
rows and joins them with tracked blocked-opportunity probes.

Development checkpoint over the trailing 24 h:

- 62 signal rows: 61 blocked / 1 executable;
- 51 blocked probes tracked: 46 resolved / 5 open;
- resolved blocked probes: 15 wins / 31 losses;
- blocked total: -7.92R; blocked expectancy: -0.17R;
- block reasons: 39 spread/stop, 22 minimum-lot risk budget;
- XAUUSD failed-auction blocked probes: +3.0R total / +0.43R expectancy across
  7 resolved probes, while capital feasibility remains the key limitation;
- XAGUSD post-shock blocked probes: negative expectancy in the same window.

These observations are diagnostics, not activation criteria. Execution remains
PAPER-only with DEMO and LIVE disabled while this work is developed.


## Capital update — 2026-09-22

Economic reference capital is now **400 EUR**.

The runtime has been updated to:

- `reference_capital_eur=400`;
- base-risk monetary budget = 4 EUR at 1%;
- absolute maximum = 8 EUR at 2%;
- daily loss maximum = 12 EUR at 3%.

At the capital-update checkpoint execution was intentionally disarmed:
`execution_mode=paper`, DEMO collection OFF, DEMO bridge OFF, LIVE OFF. This historical checkpoint is superseded by the current re-armed DEMO state documented above.

A retrospective 24 h capital-impact check shows that 11 previously
minimum-lot-blocked probes would become executable at the unchanged 1% risk.
Their aggregate result was -1.11R, so the capital increase alone is not an
activation rule. The current research priority is to select positive-edge
subsets that are now economically executable at 400 EUR.


## 400 EUR historical-admission refresh — 2026-09-22

The paired frozen-data replay was applied to the runtime admission registry after
PR #48 corrected PAPER admission semantics. The live
`strategy_admissions.json` was regenerated on 2026-09-22 and now reflects the
400 EUR economic contract.

Current PAPER eligibility across the 22 runtime mechanisms:

- BTCUSD `break_retest_reaccel` — PAPER eligible, SHADOW;
- GBPUSD `asia_range_sweep_reversal` — PAPER eligible, SHADOW;
- GBPUSD `directional_pullback_resumption` — PAPER eligible, SHADOW;
- XAUUSD `break_retest_reaccel` — PAPER eligible, SHADOW;
- XAUUSD `failed_auction_reversal` — REJECTED and PAPER ineligible.

No strategy becomes ACTIVE. LIVE remains disabled. DEMO collection is now armed, but the Portfolio Manager remains `NO_TRADE` until a collectable PAPER trade is actually open.

## Automatic execution visibility and strategy specialization — PR #50 deployed

The dashboard clarity work from PR #50 is deployed. The runtime has since been re-armed for isolated broker DEMO collection:

- reference capital 400 EUR;
- execution mode DEMO;
- DEMO collection ON;
- DEMO bridge ON;
- LIVE OFF;
- Portfolio Manager currently `NO_TRADE` while no collectable PAPER is open;
- 5/5 retained symbols READY.

The dashboard now makes this impossible to confuse with active LIVE broker trading: it shows the automatic-execution state and the actual path required before a DEMO order can be emitted.

Strategy policy is also made explicit: infrastructure is shared, but evidence is
admitted per `symbol × mechanism`. Current PAPER-eligible pairs are:

- BTCUSD: `break_retest_reaccel`;
- GBPUSD: `asia_range_sweep_reversal`, `directional_pullback_resumption`;
- XAUUSD: `break_retest_reaccel`;
- EURUSD: none;
- XAGUSD: none.

PR #52 changes isolated DEMO collection eligibility so every SHADOW row that is actually `paper_entry_allowed` can be mirrored in DEMO when its PAPER trade is open. The special `paper_collection_candidate` flag remains only the under-sampled train+validation exception; it is no longer the sole DEMO-transport gate.

Recent fixed-hypothesis research rejected three attempted shortcuts:

- EURUSD Asia sweep with a wider stop buffer: validation/holdout setups require
  a median buffer near 0.91 ATR merely to satisfy spread/stop, which deforms the
  setup;
- directional pullback with stop anchored to the last closed M15 extreme:
  worsened GBP edge and did not repair EUR/BTC;
- post-shock continuation restricted to prior same-direction M15 trend:
  BTC train/validation improved but holdout was 3/3 losses, so it was rejected.

No runtime trading threshold was changed from those tests.

## Asia midpoint-reclaim research — rejected

A fixed follow-up to `asia_range_sweep_reversal` was tested on EURUSD and
GBPUSD to improve execution geometry without weakening the 15% spread/stop
guard.

Contract:

- same completed Asia range and first qualifying sweep/reclaim;
- no entry immediately after the sweep;
- wait causally for a M5 close through the 50% midpoint of the Asia range in
  the reversal direction before 13:00 Europe/Athens;
- entry on the next M5;
- preserve the original sweep structural stop, 1.5R target, 12-M5 horizon,
  1% risk, macro and execution guards.

Result:

- EURUSD: train 11 trades / -0.116R expectancy; validation 4 / -0.471R;
  holdout 1 / +0.254R;
- GBPUSD: train 16 / +0.085R; validation 8 / -0.254R; holdout 3 / +0.100R.

The hypothesis improves executability but not robust edge, so it is rejected
and no runtime mechanism is added.


## DEMO collection eligibility expansion — PR #52 deployed

The isolated broker DEMO transport is now **armed** while LIVE remains disabled.
The pre-deploy runtime check showed:

- 5/5 retained symbols READY;
- 22 SHADOW scanners healthy;
- 0 PAPER open;
- 0 Trading-New bridge position;
- 0 pending open/close/result command;
- broker account confirmed DEMO;
- Portfolio Manager `NO_TRADE` only because no collectable PAPER is open.

PR #52 removes a policy mismatch between PAPER admission and DEMO transport.
`paper_collection_candidate` remains a special evidence flag for the
under-sampled train+validation-positive exception. It is no longer used as the
sole transport permission.

After PR #52, every SHADOW strategy for which centralized
`paper_entry_allowed()` returns true may be mirrored into isolated broker DEMO
collection when it has an open PAPER trade.

Current DEMO-collectable SHADOW set under the 400 EUR registry:

- BTCUSD `break_retest_reaccel`;
- GBPUSD `asia_range_sweep_reversal`;
- GBPUSD `directional_pullback_resumption`;
- XAUUSD `break_retest_reaccel`.

EURUSD and XAGUSD remain research-only. XAUUSD failed-auction remains REJECTED.
No risk percentage, lot floor, spread/stop threshold, stop geometry or target is
changed by this PR.


### Runtime proof after PR #52 deployment

- backend/worker restarted only after confirming 0 PAPER open, 0 Trading-New
  bridge position and 0 pending open/close command;
- execution flags preserved: DEMO mode, DEMO collection ON, DEMO bridge ON,
  LIVE OFF;
- first complete worker cycle: 22 scanners, 5/5 retained symbols READY,
  worker error null;
- 0 Trading-New bridge position, 0 pending open/close/result command;
- Portfolio Manager remains NO_TRADE only because no collectable PAPER is open;
- PAPER-eligible / DEMO-collectable SHADOW set now includes BTCUSD break/retest,
  GBPUSD Asia sweep, GBPUSD directional pullback and XAUUSD break/retest.


## Runtime market-data freshness incident — PR #54 deployed

After the DEMO collector was armed, session preflight degraded BTCUSD and
XAGUSD as `m5_stalled`. Quotes/specs were live, but the API exposed a last
closed M5 at 09:15 while the corresponding MT4 CSVs already contained 09:20,
09:25 and later bars.

This was a backend source-priority defect, not an MT4 exporter outage.

The new runtime source selector chooses the freshest causally closed source
among JSON snapshot, live `SYMBOL-TF.csv` and frozen research CSV. The
backtest/research resolver is intentionally not changed.

Pre-PR direct proof against the real MT4 directory with the patched loader:

- BTCUSD M5: 09:30;
- EURUSD M5: 09:30;
- GBPUSD M5: 09:30;
- XAUUSD M5: 09:30;
- XAGUSD M5: 09:30;
- all five live quote objects expose the same current closed-M5 timestamp.

This fix is required before further strategy work because stale runtime bars can
suppress or distort otherwise valid opportunities.


### Runtime proof after PR #54 deployment

- backend/worker restart was performed only after reconfirming 0 PAPER open,
  0 Trading-New bridge position and 0 pending command;
- execution flags remained DEMO collection ON / bridge ON / LIVE OFF;
- first complete worker cycle: 22 scanners, 5/5 retained symbols READY,
  worker error null;
- BTCUSD, EURUSD, GBPUSD, XAUUSD and XAGUSD all exposed the same current
  closed-M5 timestamp through the live API;
- session preflight returned READY with no degraded symbols;
- 0 Trading-New bridge position and no phantom open/close/result command.

Eligible-signal audit since the causal cutover found no missed executable PAPER
opportunity among the four current DEMO-collectable strategies. The only
eligible-strategy signal recorded was BTCUSD break/retest on 2026-09-20, and it
was correctly blocked because spread/stop was ~24.8%, above the unchanged 15%
ceiling.


## Current strategy-development decision — 2026-09-22

EURUSD remains research-only after three fixed specialist hypotheses failed
independent windows. BTCUSD break/retest also keeps its existing stop geometry:
a 0.80 M15-ATR minimum-stop variant improved recent execution but materially
worsened train expectancy and drawdown.

The fastest safe path to broker DEMO trading is therefore the four already
PAPER-eligible / DEMO-collectable SHADOW pairs:

- BTCUSD break/retest;
- GBPUSD Asia sweep;
- GBPUSD directional pullback;
- XAUUSD break/retest.

Runtime remains DEMO collection ON, bridge ON, LIVE OFF, with unchanged 1% base
risk and 15% spread/stop ceiling.

PR #55 was closed unmerged as an exact duplicate of already-merged PR #54.


### Runtime proof after PR #56 deployment

- pre-deploy safety check: 0 PAPER open, 0 Trading-New bridge position,
  0 pending open/close command;
- runtime SHA: `0cd45a6`;
- session preflight: READY, 5/5 retained symbols;
- DEMO mode, collection ON, bridge ON, LIVE OFF;
- Portfolio Manager: `NO_TRADE`;
- current reason: `4 PAPER-eligible SHADOW strategies are waiting for an executable PAPER trade`;
- 0 bridge positions and 0 pending broker commands.


## Manual DEMO Trade + Trade Blotter — deployed

Branch: `feat/manual-demo-trade-dashboard`.

The dashboard now exposes a dedicated manual broker-DEMO workflow without
weakening the automatic system or allowing arbitrary lot entry.

Manual workflow:

- choose BTCUSD / EURUSD / GBPUSD / XAUUSD / XAGUSD;
- choose BUY or SELL;
- enter SL and TP;
- enter risk percentage (1% default, 2% hard maximum);
- preview uses the current Bid/Ask and the central capital/risk engine;
- only an approved preview exposes the explicit `CONFIRMER DEMO` action;
- submit recomputes all guards before creating the MT4 command;
- manual positions can be closed from the dashboard only when their bridge
  comment identifies them as `TradingNew:manual_demo:*`.

A centralized Trade Blotter is also added:

- open broker Trading-New positions, labelled MANUAL DEMO or AUTO DEMO;
- PAPER positions shown separately;
- pending bridge command;
- latest bridge result;
- recent PAPER history.

Runtime proof during development used a **preview only** on live EURUSD data:

- BUY market entry: 1.14523;
- SL: 1.14423;
- TP: 1.14723;
- requested risk: 1%;
- calculated lot: 0.04;
- expected loss: 3.49 EUR;
- spread/stop: 9.0%;
- estimated margin: 4.00 EUR;
- RR: 2.00;
- preview APPROVED;
- no `trading_demo_command.csv` was created.

No real or DEMO order was sent by this validation.


### Runtime proof after PR #58 deployment

- deployed code SHA: `b07ee23`;
- backend + SHADOW worker restarted only after confirming 0 PAPER open,
  0 Trading-New bridge position and 0 pending open/close command;
- 5/5 retained symbols READY after restart;
- DEMO mode, DEMO collection ON, DEMO bridge ON, LIVE OFF;
- manual preview endpoint validated over HTTP against the live EURUSD quote;
- post-deploy preview: entry 1.14485, calculated lot 0.04,
  expected loss 3.49 EUR, spread/stop 12.0%, RR 2.00, APPROVED;
- preview created no MT4 open/close command;
- dashboard port 5180 returned HTTP 200;
- Portfolio Manager remained NO_TRADE because no collectable PAPER was open.

The manual panel is therefore deployed and ready for operator use in broker DEMO.


## Trading Intelligence v1 — 8 steps deployed

Status: **MERGED + DEPLOYED** through PR #60 at `99e2d30`.

The four currently DEMO-collectable mechanisms remain frozen. This work is
observability/research infrastructure and does not change entries, stops,
targets, admissions or risk.

The eight requested steps are implemented as follows:

1. **Trade understanding** — PAPER and blocked-probe episodes are reconstructed
   with MFE, MAE, result R, PnL when known, time-to-MFE and RR at signal/entry.
2. **Missed opportunities** — independent market-first denominator: a movement
   of at least 1.5 ATR M5 inside the following 12 M5 bars, deduplicated by the
   same horizon, then classified executable / blocked / missed.
3. **Value of waiting** — signal-to-entry delay, R lost while waiting,
   RR at signal vs entry, and MFE consumed before entry. A true pre-signal
   `first_seen` timestamp is not yet persisted and is explicitly reported as
   a limitation.
4. **DEMO execution quality** — persistent command/result audit for AUTO and
   MANUAL DEMO, with fills/refusals/errors and fill slippage in price/R.
5. **Dashboard intelligence** — consolidated 24 h intelligence panel and per-
   asset coverage table, plus recent trade/probe anatomy and qualification
   timeline.
6. **Research by asset** — each symbol is classified `COLLECT_PROSPECTIVE`,
   `DEGRADED` or `RESEARCH_ONLY` from current admission/prospective evidence, with market
   opportunities/capture/misses and next research action.
7. **Automatic qualification / degradation** — the worker records a history
   event whenever prospective evidence changes. Existing thresholds remain
   unchanged; once a strategy becomes `FAILED`, no new PAPER/DEMO entry is
   allowed, while any already-open trade continues normally to resolution.
8. **Daily report** — atomic `daily_report_latest.json` plus dated report with
   PAPER daily result, open risk, bridge latent PnL, market capture,
   qualification, execution quality and asset research state.

Real read-only development checkpoint over the latest 24 h:

- market-first opportunities: **113**;
- captured by any same-direction SHADOW signal within ±3 M5 of episode birth: **15**;
- fully missed: **98**;
- BTCUSD: 23 opportunities, 1 captured, 22 missed (4.3%);
- EURUSD: 23 / 3 / 20 (13.0%);
- GBPUSD: 23 / 3 / 20 (13.0%);
- XAUUSD: 22 / 5 / 17 (22.7%);
- XAGUSD: 22 / 3 / 19 (13.6%).

The market-first denominator is retrospective research telemetry, not a trading
signal. Its purpose is to quantify coverage before creating new mechanisms.

Performance was hardened before worker integration with a bounded recent-bar
reader. The current real 24 h calculation completes in about **0.43 s** on the
runtime host. Worker snapshots are throttled to one every five minutes.

Known limitation: the current Trading-New bridge exports open-position PnL but
does not provide reliable realized PnL for closed bridge tickets. The daily
report therefore exposes broker realized PnL as `UNKNOWN` rather than
fabricating it.


### Runtime proof after PR #60 deployment

- deployed code SHA: `99e2d30`;
- session preflight: **READY**, 5/5 retained symbols;
- SHADOW worker heartbeat: **OK**, 22 scanners, no worker error;
- execution mode: DEMO; collection ON; bridge ON; LIVE OFF;
- 0 PAPER open, 0 Trading-New bridge position, 0 pending broker command at the
  verification checkpoint;
- 4 PAPER-eligible / DEMO-collectable strategies remain unchanged:
  BTCUSD break/retest, GBPUSD Asia sweep, GBPUSD directional pullback and
  XAUUSD break/retest;
- intelligence/reporting endpoints return HTTP 200;
- qualification history is persisted and all current prospective rows remain
  COLLECTING; no strategy is currently degraded;
- execution-quality audit currently reports 0 commands / 0 fills because no
  post-PR60 DEMO command has yet been emitted;
- latest 24 h intelligence snapshot: 113 market-first episodes, 15 matched by
  SHADOW signals and 98 missed;
- full backend suite: 177 passed; Ruff clean; frontend build clean.

The intelligence layer is observability/research infrastructure. The market-first
episodes are retrospective coverage telemetry and must not be interpreted as
98 immediately tradable profitable setups.


## Market-First Signature Research — current status

A reusable offline signature analyzer was merged in PR #62 (`b126510`). It does not alter the deployed runtime or the four current DEMO-collectable mechanisms.

The first cross-asset pass found stable pre-move signature frequencies, but
causal replay rejected the obvious static mechanisms on BTC, GBP and XAU.
Therefore no new runtime strategy is being promoted from this pass.

The next research focus is event-chain structure, especially meaningful failed
auction / transition sequences, rather than further threshold tuning of generic
M5 momentum or compression patterns.


## Event-chain research checkpoint

BTC failed-auction refinement is closed after both opposite-displacement and
micro-pivot confirmation chains failed independent validation.

XAU failed-auction displacement produced positive small train/validation samples
but failed its two-trade holdout and remains mostly infeasible at the 400 EUR
risk budget because of the broker minimum lot.

No deployed strategy, risk rule or admission state changes from these tests.


## Missed Opportunity Review — dashboard follow-up

The Trading Intelligence panel now shows the 12 largest missed market-first episodes from the latest 24 h snapshot. This turns the aggregate missed-opportunity count into concrete episodes that can be inspected by asset, time and move size.

The panel remains research-only: the episode direction and magnitude are known
from the future window and are therefore never used as live trade inputs.


## Missed Opportunity Classifier v1 — deployed

Status: **MERGED + DEPLOYED** through PR #66 at `f021b98`.

The Trading Intelligence layer now classifies each market-first episode from
causal pre-move context and exposes a dashboard summary plus per-episode labels.

The first real 24 h checkpoint does **not** justify promoting a new trading
mechanism: directional displacement was more often opposed than aligned with
the future move (12 vs 16), while structural extreme/stretch was exactly split
11 vs 11. Compression contexts are common but mostly direction-neutral.

This work improves research triage only. The four current DEMO-collectable
strategies remain frozen and unchanged.


### Runtime proof after PR #66 deployment

- deployed repository SHA: `f021b98`;
- pre-deploy safety: 0 PAPER open, 0 Trading-New bridge position, 0 pending
  open/close command;
- session preflight after restart: **READY**, 5/5 retained symbols;
- SHADOW worker heartbeat: **OK**, 22 scanners, 0 worker error;
- Portfolio Manager remains `NO_TRADE` because no eligible PAPER trade is open;
- no MT4 command was created by the deployment;
- Trading Intelligence cache naturally rolled forward under the existing
  five-minute throttle; no runtime artifact was deleted or forced;
- deployed causal snapshot: 112 market-first episodes;
- unclassified: 36 episodes / 31 missed;
- directional displacement: 26 / 23 missed, 11 aligned vs 15 opposed;
- compression state: 23 / 22 missed;
- structural extreme + stretch: 13 / 9 missed, 8 aligned vs 5 opposed;
- auction failure + reclaim: 9 / 5 missed, 6 aligned vs 3 opposed;
- compression breakout: 4 / 4 missed, 0 aligned vs 4 opposed;
- structural extreme only: 1 / 1 missed;
- frontend returned HTTP 200 with the causal pattern dashboard source active;
- full validation before merge: 183 backend tests, Ruff clean, frontend build
  clean.

These counts are a rolling 24 h research snapshot and will change as the window
moves. They are not strategy admission evidence by themselves.


## Historical causal-pattern stability — PR #68 merged

Status: **MERGED** at `172b8f3`.

The causal classifier from PR #66 is now being evaluated historically over the
same frozen train / validation / holdout boundaries.

The first full five-asset pass found no directional causal class with stable
positive alignment across all windows. Compression breakout is consistently
anti-aligned, but a fixed opposite-side reversal replay failed economic
validation once broker spread, stop geometry, minimum lot and the 400 EUR risk
budget were applied.

No deployed strategy changes from this work.

Next research focus: a **Causal × Economic Candidate Matrix** that intersects
historical causal stability with broker/capital feasibility, so new mechanism
replays are attempted only where both structural information and executable
geometry coexist.


## Economic Feasibility Map — PR #69 deployed

Status: **MERGED + DEPLOYED** at `d9dca9c`.

A historical map now measures whether missed market opportunities can actually
be sized under the current broker and 400 EUR economic reference capital before
more strategy logic is attempted.

The strongest operational finding is XAGUSD: with the frozen 0.07 spread, the
15% spread/stop guard requires a stop of at least ~0.467, while 1% risk at the
0.01 minimum lot permits only ~0.08. No stop can satisfy both constraints.

Even 2% risk would only raise the ceiling to ~0.16, still infeasible. XAG should
therefore remain research-only unless broker spread/contract economics or the
economic capital base materially change; risk must not be increased merely to
force admission.

The other assets retain a feasible stop interval, but the historically viable
ATR width differs materially by asset. This reinforces per-asset strategy
specialization.

The report is now exposed through a cached, read-only API snapshot and a
Dashboard **Economic Feasibility Map**. The UI shows FEASIBLE/INFEASIBLE,
spread-imposed stop floor, minimum-lot risk ceiling, theoretical minimum
capital, best tested ATR stop width and historical approval rate. These are
execution-feasibility diagnostics only; they do not authorize higher risk or
capital changes.


### Runtime proof after PR #69 deployment

- deployed repository SHA: `d9dca9c`;
- pre-deploy safety: 0 PAPER open, 0 Trading-New bridge position,
  0 pending open/close command;
- session preflight: **READY**, 5/5 retained symbols;
- SHADOW worker heartbeat: **OK**, 22 scanners, no worker error;
- execution flags unchanged: DEMO mode, collection ON, bridge ON, LIVE OFF;
- 4 PAPER-eligible / DEMO-collectable strategies unchanged;
- `/api/v1/research/economic-feasibility`: HTTP 200;
- dashboard port 5180: HTTP 200 with Economic Feasibility Map source active;
- economic snapshot at 400 EUR / 1%:
  BTC/EUR/GBP/XAU have a non-empty feasible stop interval;
  XAG has no feasible interval;
- no strategy, admission, risk, stop, target or bridge rule changed.


## Causal × Economic Candidate Matrix — PR #71 merged

Status: **MERGED** at `d4dac43`.

The current research layer now intersects causal stability with executable
broker/capital geometry before any new mechanism replay.

The first pass finds no causal pattern that remains positively aligned with the
future move across train / validation / holdout. Several patterns are instead
consistently anti-aligned and economically feasible on BTC/EUR/GBP/XAU.

This does not promote a reversal strategy automatically. It narrows the next
research hypotheses to cells where both structural consistency and executable
geometry exist. The next concrete replay target is GBPUSD
`structural_extreme_stretch` as an opposite-side structural mean-reversion
hypothesis, because that cell is stable across all three windows and was not
already rejected by the earlier compression/displacement replays.


## Matrix-guided replay checkpoint

The first two economically feasible OPPOSED_STABLE cells were replayed as fixed
mean-reversion contracts and both failed all independent windows:

- GBP structural extreme stretch reversal;
- XAU directional displacement reversal.

No strategy is promoted. The evidence now rejects single-state causal labels as
sufficient entry logic.

Next chantier: **Causal Sequence Research v1**, using ordered pre-move context
states across multiple M5 bars rather than adding more static thresholds.


## Dashboard UX — PR #73 deployed

Status: **MERGED + FRONTEND ACTIVE** at `cf05e90`.

The dashboard is being reorganized around operational decisions instead of one
long stack of technical panels.

The default view now answers the immediate questions first:

- is the runtime healthy?;
- is automatic DEMO transport armed?;
- does Trading-New have an open broker position?;
- what is today's PAPER PnL?;
- are executable opportunities present?;
- is macro clear?;
- how far has prospective evidence progressed?

Detailed execution, market and research information remains available through
separate top-level views. This is a presentation-only change and does not alter
trading authority or evidence policy.


## Causal Sequence Research v1 — PR #74 merged

Status: **MERGED** at `b5388e4`.

Research now evaluates ordered three-M5 causal contexts instead of isolated
states. The report measures both directional MFE lift and a stricter symmetric
first-touch lift on **all sequence occurrences** relative to each asset's own
train / validation / holdout baseline.

The strict screen left only one BTC and one XAU sequence with >50% first-touch
success in all three windows and minimum sample support. Actual cost-aware
replays rejected both because train expectancy stayed negative.

No runtime strategy is promoted. Current automatic DEMO collection remains
unchanged and continues waiting for one of the four existing PAPER-eligible
strategies to produce an executable PAPER trade.


## Next research chantier

**Execution-Aware Sequence Research**.

PR #74 showed that directional and symmetric first-touch lifts can still select
sequences that fail once real entry, spread and asset-specific stop geometry are
applied. The next layer therefore moves executable path economics into the
sequence-screening stage itself.

No runtime change is authorized from PR #74. Automatic DEMO collection remains
limited to the existing four PAPER-eligible strategies.


## Execution-Aware Sequence Research — PR #76 merged

Status: **MERGED** at `3251b41`.

Broker/capital economics are now moved inside the sequence-discovery stage rather
than applied only after statistical selection.

The first strict pass leaves one implementation candidate:

- BTCUSD;
- causal sequence:
  `structural_extreme -> directional_displacement ->
  directional_displacement`;
- fixed stop: 1.5 ATR M5;
- target: 1.0R;
- horizon: 12 M5;
- next-M5 entry;
- unchanged frozen spread/slippage, 400 EUR / 1% sizing, macro and broker guards.

The sequential replay stays positive on train / validation / holdout, but train
edge is marginal and independent sample sizes remain below ACTIVE admission
minimums. Therefore no execution activation is authorized.

If implemented next, it must be a BTC-only SHADOW/PAPER collector with explicit
runtime/backtest parity tests and unchanged LIVE lock.


## BTC structural displacement sequence — PR #77 deployed

Status: **MERGED + DEPLOYED** at `17a1bbb`.

The execution-aware research candidate from PR #76 is now implemented as a
separate BTC-only mechanism, not as a modification of an existing family.

Observed deployed impact:

- SHADOW scanners: 22 -> **23**;
- runtime scope: exactly one additional scanner, BTCUSD only;
- admission: **SHADOW**;
- PAPER collection candidate: **yes**;
- ACTIVE: **no**;
- LIVE: unchanged / locked.

Backtest/runtime parity is enforced through a common causal-sequence detector.
Unit tests also lock BTC-only scope, registry parsing, no-future-bar behavior,
1.5 ATR stop geometry, 1R target, 12-M5 horizon and the under-sampled SHADOW
admission contract.

Deployment completed after CI and a 0-open-position / 0-pending-command safety check. The mechanism remains SHADOW/PAPER-only; no ACTIVE or LIVE authority was created.


## Shadow worker singleton hardening — PR #78 deployed

Status: **MERGED + DEPLOYED** at `92ce5c6`.

A duplicate Trading-New SHADOW worker was detected on 2026-09-22 while the
runtime had 0 open PAPER trades, 0 Trading-New bridge positions and 0 pending
broker commands. The orphan process was stopped immediately; the remaining
canonical worker stayed healthy and the session remained 5/5 READY.

The runtime is being hardened with two independent protections:

1. the worker holds an OS-level `flock` for its entire process lifetime, so a
   second worker cannot operate on the same shadow ledger;
2. the startup watchdog refuses to spawn a replacement if the prior worker PID
   does not actually terminate.

This is an operational safety fix only. The deployed 23-scanner strategy scope,
five PAPER-eligible SHADOW collectors, 400 EUR risk contract and LIVE lock are
unchanged.

Validation on the PR branch: 211 backend tests passed, Ruff clean,
`start_trading.sh` syntax clean and frontend build clean.


### Runtime proof after PR #78 deployment

- pre-restart safety: 0 PAPER open, 0 Trading-New bridge position,
  0 pending broker command;
- one canonical SHADOW worker remains;
- worker lock file points to the active worker PID;
- a deliberate second-worker launch exits immediately with
  `shadow worker already running`;
- session preflight: **READY**, 5/5 retained symbols;
- SHADOW heartbeat: **OK**, 23 scanners, 0 worker error;
- 5 PAPER-eligible SHADOW collectors:
  BTC break/retest, BTC structural displacement sequence,
  GBP Asia sweep, GBP directional pullback and XAU break/retest;
- frontend Command Center remains active on port 5180;
- LIVE remains OFF.


## 2026-09-22 — reprise post-PR #79

Verification de reprise effectuee avant toute nouvelle modification :

- `origin/main` = `a3fb3bd` (PR #79, documentation du deploiement #78) ;
- PR #73 bien incluse dans `main` et **Command Center actif** sur le frontend `:5180` ;
- frontend servi depuis `/home/laetitia/trading/Trading/frontend`, HTTP 200 ;
- source Vite active contenant `Vue d’ensemble`, `Marches`, `Recherche` et
  `Details techniques par actif` ;
- backend et worker laisses intacts ; aucun restart necessaire ;
- preflight runtime **READY 5/5** ;
- capital de reference 400 EUR, risque de base 1 %, DEMO collection ON,
  bridge ON, LIVE OFF ;
- 23 fichiers PAPER courants controles, tous avec `open_trade = null` ;
- le worktree temporaire `Trading-dashboard` etait propre et a ete supprime
  apres confirmation du frontend actif.

Le chantier `Causal Sequence Research v1` n etait plus en etat partiel : il a
ete fusionne via #74, puis prolonge par #76 (execution-aware), #77 (collecteur
BTC SHADOW/PAPER) et #78/#79 (singleton worker + documentation).

Validation de reprise : 17 tests cibles sequence/execution/parite passent.
Aucun changement de runtime, risque, sizing, stop, target, spread ou LIVE n a
ete effectue pendant cette reprise.


## 2026-09-23 — DEMO readiness / no-trade visibility

Runtime diagnosis confirmed before modification:

- session READY 5/5, worker healthy;
- DEMO collection ON, bridge ON, LIVE OFF;
- 23 PAPER states checked, 0 open trade;
- 5 SHADOW collectors are currently PAPER/demo-collection eligible;
- portfolio action remains NO_TRADE only because none of those five collectors currently has an executable PAPER trade;
- the 24 h opportunity funnel can contain executable signals from non-qualified strategies; those remain intentionally excluded from broker execution.

The DEMO execution status now distinguishes four concepts instead of collapsing them into a single ready boolean:

- transport armed;
- automatic collection armed;
- waiting for a qualified trade;
- current order ready.

The Command Center uses this distinction and shows qualified executable opportunities versus all executable opportunities over 24 h. It also provides a direct navigation action to the existing guarded manual DEMO form. Manual submission still requires preview + explicit confirmation and remains blocked by the existing risk, macro, PAPER-position and Trading-New isolation guards.

No admission, signal threshold, spread threshold, risk fraction, lot rule, cap, LIVE flag or broker isolation rule changes in this chantier.


## 2026-09-23 — XAU Asia sweep prospective collector

Single-hypothesis extension under validation: enable the existing asia_range_sweep_reversal mechanism on XAUUSD for SHADOW/PAPER evidence collection only.

Historical replay at the unchanged 400 EUR / 1% contract:

- 68 candidates, 12 executable, 56 rejected by minimum-lot risk geometry;
- train: 8 trades, -0.375R expectancy, PF 0.500;
- validation: 2 trades, +1.500R expectancy;
- holdout: 2 trades, +0.250R expectancy, PF 1.500;
- admission remains SHADOW / insufficient independent evidence;
- current policy allows prospective PAPER collection because independent validation and holdout expectancy are positive.

The runtime scope change is limited to allowing Asia sweep on GBPUSD + XAUUSD. Directional pullback remains GBP-only. Risk, entry logic, stop, target, macro, sizing, spread guards, LIVE lock and broker isolation are unchanged.

Dry-run against current MT4 data in /tmp: 24 diagnostics total versus 23 deployed, with exactly one additional XAUUSD Asia sweep scanner; current XAU state is NO_SIGNAL.


## 2026-09-23 — PR #82 deployed

Status: **MERGED + DEPLOYED** at `5a2782f`.

Deployment safety immediately before the worker restart:

- 23 current PAPER state files inspected directly, 0 open trade;
- `demo_collection_state` empty;
- 0 Trading-New bridge position;
- no pending Trading-New open/close command.

Only the SHADOW worker was restarted. Backend and frontend were left running. The singleton lock moved cleanly to the new worker PID.

First completed post-deployment cycle:

- session READY 5/5, worker OK;
- scanners: 23 -> **24**;
- PAPER states: 23 -> **24**;
- XAUUSD now has an `asia_range_sweep_reversal` SHADOW/PAPER scanner and state;
- PAPER/demo-collection eligible collectors: 5 -> **6**;
- current XAU Asia sweep state: NO_SIGNAL;
- 0 PAPER open, 0 Trading-New broker position, 0 pending command;
- AUTO-DEMO transport and collection remain armed; LIVE remains OFF.

The new collector does not create ACTIVE authority. It exists only to accumulate prospective evidence under the unchanged 400 EUR / 1% contract.


## 2026-09-23 — unqualified executable research probes

A learning gap was identified after PR #82: executable SHADOW signals from strategies that are not PAPER-admitted are counted by the funnel but previously had no future R outcome recorded. Only economically blocked signals had counterfactual probes.

The new research-probe layer tracks these executable-but-unqualified signals prospectively with the exact existing PAPER resolution engine, but writes to isolated `*_unqualified_probe_state.json` / `*_unqualified_probes.jsonl` files.

Safety contract:

- these files do not match the `*_paper_state.json` registry;
- they cannot enter Portfolio Manager selection;
- they cannot be mirrored by DEMO collection;
- they do not change admissions automatically;
- no risk, lot, spread, stop, target, macro or LIVE rule changes.

Opportunity Funnel now exposes separately the number of unqualified executable probes, resolved/open counts, R expectancy and win/loss evidence. The dashboard Research view surfaces the same information.


## 2026-09-23 — PR #84 executable-unqualified probes deployed

Status: **MERGED + DEPLOYED** at `13398a3`.

Deployment safety was checked directly from runtime artifacts immediately before each required restart:

- 24 current `*_paper_state.json` files, 0 open PAPER trade;
- empty `demo_collection_state`;
- 0 Trading-New bridge position;
- no pending Trading-New open or close command;
- one broker-observed position belonging outside the Trading-New bridge remained untouched.

Deployment scope:

- backend restarted to expose the extended Opportunity Funnel API;
- SHADOW worker restarted under the singleton guard to activate prospective unqualified executable probes;
- frontend process was not restarted; Vite serves the merged Command Center source from `main`;
- LIVE remained OFF.

Post-deployment proof:

- session READY 5/5 and worker heartbeat OK;
- 24 SHADOW scanners unchanged;
- 6 qualified PAPER/demo-collection collectors unchanged;
- 18 isolated `*_unqualified_probe_state.json` files created only for non-PAPER-admitted scanner pairs;
- 0 unqualified trade result at the first cycle because no signal was present at that instant;
- 0 PAPER open, 0 Trading-New broker position and 0 pending command after deployment.

This layer cannot enter Portfolio Manager selection or the DEMO bridge. Its purpose is to measure the future R of technically executable signals that were previously counted but not resolved, so research can identify additional collector candidates from prospective evidence without relaxing admission or risk.


## 2026-09-23 — unqualified-probe research qualification

A read-only qualification layer is being added on top of PR #84 probe evidence. It reuses the existing prospective contract (20 resolved trades, positive expectancy, PF >= 1.05, DD <= 12R) but maps a passing result to `SUPPORTS_REVIEW`, never to PAPER/DEMO authority.

Safety semantics:

- `COLLECTING`: insufficient resolved executable-probe evidence;
- `FAILED`: the existing prospective quality contract is not met;
- `SUPPORTS_REVIEW`: evidence is sufficient only to trigger a dedicated single-family validation step;
- no admission file, Portfolio Manager state, PAPER permission, DEMO bridge or LIVE flag is modified automatically.

Validation on the isolated branch: 219 backend tests pass, Ruff clean and frontend build clean. A read-only calculation over current production data detected one open unqualified probe, `XAUUSD:post_shock_continuation`, correctly reported as `COLLECTING 0/20`.


## 2026-09-23 — PR #86 probe qualification deployed

Status: **MERGED + DEPLOYED** at `2bd46db`.

The backend was restarted only after a direct safety check confirmed 24 PAPER states with 0 open PAPER trade, empty DEMO collection state, 0 Trading-New bridge position and no pending open/close command. The SHADOW worker was not restarted because PR #86 changes only read-only funnel qualification and frontend presentation.

Post-deployment:

- READY 5/5, worker healthy, AUTO-DEMO armed, LIVE OFF;
- dashboard exposes research-only review readiness and per-family `n/20` progress;
- first live executable-unqualified probe is `XAUUSD:post_shock_continuation`, SELL, still open and correctly research-only;
- current review-ready family count = 0;
- 0 PAPER open, 0 Trading-New broker position, 0 pending command.

A follow-up copy fix ensures COLLECTING/FAILED reasons explicitly say executable-probe evidence rather than PAPER evidence. This does not alter any qualification threshold or authority.


## 2026-09-23 — Command Center research-progress candidate

The Opportunity Funnel now exposes the most-observed executable-unqualified research candidate as a dedicated read-only object. Selection is intentionally based on resolved sample count, not on PnL ranking, so small positive/negative samples are not presented as a best strategy.

The Command Center Overview shows symbol, mechanism, `n/20` progress, research state and current probe expectancy.

Current production read-only result at validation time:

- `XAUUSD:post_shock_continuation`;
- `COLLECTING 1/20`;
- expectancy = -1.0R;
- review-ready strategies = 0.

This is visibility only. It does not change admission, PAPER/DEMO authority, risk, sizing, signal detection or LIVE.


## 2026-09-23 — first automatic broker DEMO execution observed

Trading-New has now completed its first qualified automatic DEMO entry path.

- strategy: `BTCUSD:structural_displacement_sequence`;
- PAPER signal: SELL at 2026-09-23 09:30 Europe/Athens;
- PAPER reference entry 86398.00, SL 86581.2868, TP 86214.7132;
- broker DEMO ticket 185258524 filled at 86385.37 for 0.02 lot;
- broker SL 86581.29 / TP 86214.71;
- fill-based theoretical stop loss is about 3.43 EUR versus the 4 EUR base-risk budget;
- LIVE remains OFF.

The position is currently owned by the Trading-New bridge. While its PAPER/broker
position is open, no merge, deployment or runtime restart is authorized.

A separate isolated branch adds a guarded manual handoff from a currently
`signal_executable` opportunity to the existing DEMO preview. It never submits
an order directly: the backend recomputes target geometry from the live broker
quote and the signal stop/target-R, then the existing explicit confirmation is
still required.
## 2026-09-23 — broker fill risk fidelity candidate

The first automatic DEMO execution proved the broker path works, but also exposed
normal market-fill drift between the PAPER reference entry and the broker fill.

Observed first BTC sequence trade:

- PAPER reference risk: about 3.21 EUR;
- broker-fill stop risk: about 3.43 EUR;
- base risk budget: 4.00 EUR;
- PAPER target geometry: 1.00R;
- broker-fill reward/risk geometry: about 0.87R.

The current trade remains inside the monetary risk budget, but the execution
audit is being extended so every future fill records these deltas automatically.
This is measurement only; sizing, SL, TP, risk policy and bridge behavior remain
unchanged. Deployment is blocked while the current Trading-New position is open.
## 2026-09-23 — runtime drain control candidate

Trading-New previously had no real deployment drain. The nearest static setting
(`demo_collection_enabled`) is process-loaded and therefore unsuitable for safe
hot deployment control.

A dedicated runtime drain is now implemented on an isolated branch:

- persistent `shadow/drain_state.json`;
- hot GET/POST API at `/api/v1/runtime/drain`;
- worker reloads drain state every cycle without restart;
- DRAIN ON blocks new PAPER entries;
- DRAIN ON blocks new automatic broker DEMO entries;
- DRAIN ON blocks manual DEMO preview/submission;
- already-open PAPER and broker DEMO positions continue to resolve and close;
- research scanners, blocked probes and executable-unqualified probes continue
  collecting evidence;
- dashboard Trading view exposes explicit DRAIN ON / DRAIN OFF controls with
  confirmation.

Validation: 34 targeted drain tests, 224 full backend tests, Ruff clean and Vite
build clean. The feature is not deployed while the current Trading-New BTC
PAPER/broker position remains open.


## 2026-09-23 — PR #92 deployed, drain released, first broker cycle reconciled

PR #92 is **MERGED + DEPLOYED** at `cd779ea`.

Deployment procedure:

- Trading-New book confirmed flat before merge/restart;
- native runtime drain created ON before process restart;
- exact pre-drain admission registry restored and verified with `cmp`;
- backend, SHADOW worker and frontend restarted once;
- post-deploy READY 5/5, 24 scanners, 6 qualified collectors, 0 PAPER open,
  0 bridge position and 0 pending open/close command;
- native DRAIN then switched OFF through `/api/v1/runtime/drain`;
- auto-DEMO is armed again and LIVE remains OFF.

First automatic broker DEMO cycle is now fully observed:

- strategy: `BTCUSD:structural_displacement_sequence`;
- PAPER: timeout close at 86292.60, +0.5751R, +1.8453 EUR;
- broker ticket 185258524: open 86385.37, close 86234.48, realized +2.64 EUR;
- broker history magic = 560619, proving ownership by Trading-New.

P0 follow-up adds ticket-driven MT4-history reconciliation so broker realized PnL
is reported exactly when every closed Trading-New ticket is present, and remains
UNKNOWN if any closed ticket is missing.
## 2026-09-23 — P1 executable-probe review queue candidate

The prospective executable-unqualified probe layer now exposes an explicit
research review queue.

A strategy enters this queue only when its existing probe qualification reaches
`SUPPORTS_REVIEW` (minimum 20 resolved probes + the unchanged prospective
expectancy/PF/DD contract). The queue exposes strategy id, symbol, mechanism,
sample size, expectancy, profit factor and drawdown.

This remains research-only: queue membership does not modify admission files,
PAPER authority, DEMO collection, risk, sizing or LIVE.


## 2026-09-23 — P2/P3 research outcome + Trailing Manager chantier

Two fixed, causal inter-market hypotheses were tested with unchanged XAU signal
geometry, frozen execution costs and the existing 400 EUR / 1% policy.

### P2 — XAU failed-auction × USD pressure

Filter: on the last three closed M5 bars before entry, EURUSD and GBPUSD must
both confirm the expected USD direction (both rising for XAU BUY / USD weakness,
both falling for XAU SELL / USD strength).

Execution-aware results:

- train: 16 trades, +0.1643R expectancy;
- validation: 27 trades, -0.1290R;
- holdout: 12 trades, -0.5059R.

Decision: **REJECTED**. No runtime filter or admission change.

### P3 — XAU post-shock × USD pressure

Same fixed inter-market confirmation, different family after P2 rejection:

- train: 3 trades, -0.0667R;
- validation: 7 trades, -0.6000R;
- holdout: 3 trades, -1.0000R.

Decision: **REJECTED**. No new collector is activated. Useful trade frequency
cannot be manufactured by accepting negative independent evidence.

### Planned chantier — Trailing Manager

A new exit-management research track is now scheduled. Safety contract:

1. initial monetary risk is immutable;
2. trailing SL may only preserve or reduce initial loss; it may never widen;
3. target changes are evaluated causally from closed market bars only;
4. target extension cannot justify increasing stop risk;
5. first implementation is replay-only, then SHADOW hypothetical adjustments,
   then PAPER; broker DEMO modification is forbidden until those stages prove
   improved expectancy / drawdown without hidden risk;
6. one family at a time, with static-exit control vs trailing-exit treatment.

The intended manager will study market-structure / ATR / favorable-excursion
state to move SL and TP with the market, rather than using a fixed-distance
trailing stop.


## 2026-09-23 — P0–P3 completed + Trailing Manager v0 candidate

The four post-first-trade development steps are now closed at their current
evidence stage:

- P0 broker reconciliation: MERGED + DEPLOYED through PR #95; first automatic
  Trading-New ticket reconciles exactly from MT4 history at +2.64 EUR realized;
- P1 executable-probe review workflow: MERGED + DEPLOYED through PR #95;
  SUPPORTS_REVIEW remains research-only and now has an explicit dedicated replay
  workflow;
- P2 XAU failed-auction x USD-pressure confirmation: REJECTED because validation
  and holdout are negative;
- P3 XAU post-shock x USD-pressure confirmation: REJECTED on train, validation
  and holdout; no frequency collector was added.

PR #93 has been closed as superseded by merged integration PR #95.

### Trailing Manager v0

The first exit-management family is deliberately limited to
`BTCUSD:structural_displacement_sequence`.

Paired replay keeps exactly the same accepted entries, sizing, execution costs,
macro exclusions and static overlap decisions. Only exit management changes.

SL-only causal trailing (3-bar structure + ATR buffer + break-even protection):

- train: +0.0122R static -> +0.0067R trailing;
- validation: +0.1384R -> +0.0925R;
- holdout: +0.2015R -> +0.1199R;
- decision: REJECTED despite lower drawdown in train/holdout.

TP-only dynamic extension, with initial SL unchanged:

- trigger uses closed bars only, favorable progress + directional close sequence;
- initial 1.0R target may extend to 1.5R;
- train: +0.0122R -> +0.0424R;
- validation: +0.1384R -> +0.1717R;
- holdout: +0.2015R -> +0.2571R;
- drawdown is unchanged in all three windows;
- 10 historical trades triggered an adjustment, 5 improved and 0 worsened;
- no initial-risk increase occurred.

This is promising but still too small for broker TP modification. The next stage
is prospective SHADOW evidence only.

The candidate adds an isolated trailing-shadow ledger and state. The first live
cycle establishes its own prospective start time; historical PAPER trades are
never backfilled. Completed future BTC structural-displacement PAPER trades are
replayed only after their complete original horizon is available. PAPER, bridge,
SL and TP are never modified.

Validation: 8 targeted tests, 241 full backend tests, Ruff clean, Vite build
clean. A real-data /tmp dry-run starts at 0 resolved observations and performs no
production-runtime write.


## 2026-09-23 — PR #96 deployed + runtime stop hardening

PR #96 `Add prospective Trailing Manager research` is **MERGED + DEPLOYED**
at `bf6f00a`.

Deployment proof:

- Trading-New book flat before deployment;
- native drain ON before merge/restart;
- 24 scanners / 6 PAPER-eligible collectors preserved;
- READY 5/5 after deployment;
- LIVE OFF;
- 0 PAPER open, 0 Trading-New bridge position, 0 pending open/close command;
- Trailing SHADOW state initialized prospectively at
  2026-09-23T17:33:37+03:00;
- initial trailing evidence = 0 resolved observations, proving no historical
  backfill;
- Research dashboard exposes the TP-dynamic trailing progress card;
- drain released OFF after verification; auto-DEMO armed again.

During the restart verification an operational defect was found: backend port
8020 was still served by an older Trading uvicorn process because the previous
backend PID file was missing. Frontend and worker had restarted, but the stale
backend continued serving the old API until explicitly replaced. No trade or
command was open and the drain remained ON throughout the correction.

A follow-up hardens `ops/stop_trading.sh`:

- PID files remain the first stop mechanism;
- missing/stale PID files now trigger a safe process fallback;
- orphan backend/frontend listeners are killed only when both process cwd and
  expected command match this Trading repo;
- orphan worker cleanup additionally requires a real Python executable, matching
  backend cwd and `-m app.shadow_worker`;
- unexpected listeners are refused rather than killed;
- backend/frontend ports honor the same configurable env vars as start script;
- stop waits for process exit and fails closed if a process refuses to stop.

Validation: isolated orphan backend/worker/frontend cleanup PASS on temporary
ports, `bash -n` clean, executable mode preserved, and 241 backend tests pass.


## 2026-09-23 — Trailing Manager protective-stop follow-up

A third incremental replay was tested on the same paired
`BTCUSD:structural_displacement_sequence` entries.

Baseline for this comparison is the already-promising TP-only policy. The only
new behavior is that, once the target has been extended, the stop may tighten
toward structure / break-even. The stop cannot move before target extension and
can never increase initial risk.

Results versus TP-only:

- train: expectancy 0.0424R -> 0.0653R; max DD 5.0464R -> 4.6879R;
- validation: expectancy 0.1717R -> 0.1717R; DD unchanged;
- holdout: expectancy 0.2571R -> 0.2571R; DD unchanged;
- 0 added-risk violations.

Decision: **REJECTED FOR PROSPECTIVE ACTIVATION**. The extra SL protection has no
incremental validation or holdout benefit. The deployed Trailing SHADOW remains
TP-only. The protective-stop mode stays research-only for future evidence.

## 2026-09-23 — post-PR #98 operational checkpoint

PR tracking:

- #95 `Integrate broker PnL reconciliation and probe review workflow`: MERGED + DEPLOYED at `ac2c0e9`;
- #96 `Add prospective Trailing Manager research`: MERGED + DEPLOYED at `bf6f00a`;
- #97 `Harden runtime stop against orphaned processes`: MERGED at `bf35db2`; shell deployment utility is active on disk and requires no process restart;
- #98 `Evaluate protective stop after target extension`: MERGED at `85c6a97`; research-only code, no runtime authority change and no restart required;
- #93 was closed as superseded by integration PR #95.

Current runtime after all deployment checks:

- session READY 5/5;
- worker healthy;
- 24 SHADOW scanners;
- 6 PAPER/demo-collection eligible strategies;
- DEMO transport ON, auto-DEMO collection armed;
- DRAIN OFF;
- LIVE OFF;
- 0 PAPER open;
- 0 Trading-New broker position;
- 0 pending Trading-New open/close command.

First automatic Trading-New cycle remains fully reconciled:

- PAPER +1.8453 EUR / +0.5751R;
- broker DEMO realized +2.64 EUR;
- broker history complete = true;
- 1 closed Trading-New broker ticket reconciled;
- observed broker-fill RR moved from planned 1.00R to 0.871R.

Current 24 h research denominator:

- 112 market opportunities;
- 17 captured;
- 95 missed.

Executable-unqualified prospective evidence:

- 17 resolved probes;
- 5 wins / 12 losses;
- -4.7805R total;
- -0.2812R expectancy;
- research review queue = empty;
- most-observed family = `BTCUSD:failed_auction_reversal`, 3/20 probes, -0.1667R expectancy;
- `BTCUSD:directional_transition` is +1.21R but on only 2 resolved probes, therefore non-actionable.

Trailing Manager prospective state:

- strategy: `BTCUSD:structural_displacement_sequence`;
- prospective start: 2026-09-23T17:33:37+03:00;
- resolved future observations: 0;
- deployed policy: TP dynamic extension only;
- SL trailing remains inactive because both tested SL policies failed the independent-evidence gate.

Next evidence gates:

1. keep the six qualified collectors running unchanged;
2. automatically review any executable-probe family only after `SUPPORTS_REVIEW`;
3. accumulate future Trailing SHADOW results before any PAPER-stage exit change;
4. never promote frequency, trailing SL/TP or LIVE from small positive samples.
