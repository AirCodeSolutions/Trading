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

Current deployed main commit: `6a7e8e6` (PR #52).

Operational services:

- frontend: port 5180
- backend: port 8020
- SHADOW worker: 22 active scanners
- 22 active SHADOW scanners: 5 markets × 4 baseline mechanisms + GBPUSD directional pullback + GBPUSD Asia range sweep
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
- latest checked state: 22 scanners, 5/5 READY, 0 worker error, 0 PAPER open, 0 Trading-New command/position; DEMO guard waits only for a portfolio-selected collectable PAPER trade.

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


## Runtime market-data freshness incident — PR #54 in flight

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
