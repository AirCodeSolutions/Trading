# Post-V2 Economic Acceleration — P0 to P2

Date: 2026-10-01
Scope: Trading-New only

## Objective

Increase durable risk-adjusted broker-net PnL without weakening the existing
risk, sizing, spread, 5-lot, macro or broker-ownership safeguards.

The V2 architecture is complete. This chantier is economic, not architectural.
Every PR changes or measures one economic hypothesis only.

## P0 — Highest priority

### P0-A — Paired PAPER economic contracts

Status: IN PROGRESS

Family: XAUUSD:structural_displacement_sequence

Champion:
- contract id: xau_sd_target_1r_v1
- target: 1.0R

Challenger:
- contract id: xau_sd_target_1_5r_v2
- target: 1.5R

Pairing rules:
- same signal;
- same entry;
- same structural stop;
- same lots and monetary risk;
- same opened_at;
- same 12-M5 safety horizon;
- target is the only changed economic variable;
- no new pair starts while either side of the previous pair remains open;
- drain prevents new pair entry but existing pair members may resolve;
- paired metrics ignore orphan/unmatched outcomes;
- broker_authority=false and human_review_required=true.

Exit criteria:
- prospective paired N reaches the existing review minimum;
- compare expectancy, PF, DD and total delta R;
- no automatic promotion.

### P0-B — Versioned economic contracts and clean cutovers

Status: IN PROGRESS

Every material economic change receives a stable contract id/version.
Evidence produced under different target/stop/trigger/exit contracts must never
be mixed in one canonical prospective cohort.

The existing XAU structural-displacement 1.0R evidence remains legacy when a
1.5R canonical cohort eventually starts.

## P1 — Evidence and selection quality

### P1-A — Authority regret ledger

Status: QUEUED

For every executable opportunity, preserve the contemporaneous authority
decision and future resolved outcome. Measure separately:
- losses avoided by authority;
- winners missed by authority;
- accepted winners;
- accepted losers;
- R and broker-cost-adjusted R by reason.

No authority rule changes in the measurement PR.

### P1-B — Controlled admission refresh

Status: QUEUED

Recompute runtime historical admissions from actual MT4 DEMO equity on a
controlled cadence using the frozen split and existing thresholds.
The refresh remains research/admission only and never promotes directly to
broker authority.

Exit criteria:
- deterministic output;
- atomic registry replacement;
- no heartbeat blocking;
- explicit diff old/new admissions.

### P1-C — Regime/session attribution

Status: QUEUED

Test whether family edge is concentrated by causal session/regime using fixed
pre-registered partitions. No threshold tuning after outcome inspection.

Start with XAU structural displacement only.

## P2 — Robustness

### P2-A — Execution-cost stress

Status: QUEUED

Replay candidate families under observed costs plus pre-registered adverse-cost
scenarios. A family is not considered robust if its edge disappears under a
reasonable spread/slippage deterioration.

### P2-B — Family-specific exit challengers

Status: QUEUED

Only create an exit challenger when measured giveback/no-follow-through supports
a specific hypothesis. No generic Position Manager rollout.

Current evidence:
- Position Manager V2 is rejected for XAU structural displacement as a wholesale
  replacement: validation and full-history performance degrade despite a holdout
  improvement.

## Invariants

- Trading-New only.
- MT4 DEMO only; LIVE remains OFF.
- max 5 lots per trade.
- no artificial daily trade cap.
- no daily-loss broker veto.
- actual MT4 DEMO equity first, balance fallback, no fixed research capital in
  runtime sizing/admission refresh.
- spread guard remains 0.15.
- no risk increase without proof.
- no merge/pull/restart while Trading-New deployment book is not flat.
- drain ON -> BOOK_FLAT -> deploy -> postflight -> drain OFF.
- research/PAPER changes never imply broker authority.
