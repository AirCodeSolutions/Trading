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

Status: IMPLEMENTED — VALIDATION GREEN, PR PENDING

The report reuses persisted Trading-New ledgers and keeps three populations
strictly separate:
- executable opportunities rejected from PAPER authority;
- accepted PAPER outcomes, with exact DEMO-executed tagging when the PAPER trade
  id appears in the DEMO collection completion ledger;
- economically blocked probes, which remain guard counterfactuals and are never
  counted as executable authority regret.

Measured outputs include:
- losses avoided by authority;
- winners missed by authority;
- accepted winners and losers;
- rejected counterfactual total R;
- guard-blocked counterfactual R by persisted block reason;
- by-strategy and by-reason attribution.

Persisted PAPER/probe R is already spread-aware through its executable geometry.
Counterfactual observations do not have exact broker fills, so slippage and
commissions are not invented: broker_cost_adjusted_r remains unavailable unless
an exact broker fill can be paired.

No admission, PAPER, portfolio, risk, sizing or broker authority rule changes in
this measurement PR.

### P1-B — Controlled admission refresh

Status: IMPLEMENTED — VALIDATION IN PROGRESS

The refresh is now split into two explicit operations:
- PREVIEW: rerun the frozen historical research with actual MT4 DEMO
  equity/balance and show the exact old/new admission diff without writing;
- APPLY: rerun the same contract and atomically replace the registry only when
  drain is ON, Trading-New BOOK_FLAT is proven and no active symbol was skipped.

The workflow preserves:
- the frozen research split;
- current risk fraction and five active assets;
- actual DEMO equity/balance capital source;
- atomic strategy_admissions.json replacement;
- an atomic runtime_admission_refresh_receipt.json receipt;
- no heartbeat or shadow-worker refresh loop;
- no direct broker promotion.

The dashboard exposes PREVIEW only. APPLY remains an operator/deployment action.

Exit criteria:
- deterministic output;
- atomic registry replacement;
- no heartbeat blocking;
- explicit diff old/new admissions;
- fail-closed on drain OFF, non-flat book, unavailable DEMO capital or skipped
  active symbols.

### P1-C — Regime/session attribution

Status: IMPLEMENTED — VALIDATION IN PROGRESS

Scope is frozen to XAUUSD structural displacement 1.5R. Attribution uses the
existing causal session contract and the existing M15 regime classifier.

Pre-registered partitions:
- sessions: asia, london, us, transition;
- regimes: warmup, dead, balanced_auction, directional_expansion, post_shock;
- windows: validation and holdout remain separate.

No session×regime cross-product, ranking or automatic gate is produced.

Current actual-equity replay reconstructs exactly 25 validation and 14 holdout
trades. Descriptively:
- Asia, London and US are positive in both independent windows;
- transition is +3R on only 2 validation trades and -1R on only 1 holdout trade;
- balanced_auction contains most observations and is positive in both windows;
- directional_expansion is positive on 2 validation trades but -1R on only
  1 holdout trade.

These small cells are not sufficient to create a session/regime veto.

## P2 — Robustness

### P2-A — Execution-cost stress

Status: COMPLETE — MERGED / DEPLOYED — PR #203

Scope: XAUUSD structural displacement under the canonical 1.5R contract.

Pre-registered scenarios:
- OBSERVED: spread 1.00x, slippage 0.25x spread;
- ADVERSE_25: spread 1.25x, slippage 0.50x spread;
- ADVERSE_50: spread 1.50x, slippage 1.00x spread.

Observed result:
- OBSERVED validation +0.423R / PF 2.46; holdout +0.661R / PF 3.31.
- ADVERSE_25 validation +0.400R / PF 2.37; holdout +0.473R / PF 2.32.
- ADVERSE_50 validation +0.312R / PF 2.05; holdout +0.458R / PF 2.28.

All three scenarios remain positive in both frozen windows. The report is
Research-only, authority_effect=false, and changes no live spread guard,
admission, PAPER or broker authority.

### P2-B — Family-specific exit challengers

Status: ACTIVE — hypothesis 1 REJECTED, champion unchanged

Only create an exit challenger when measured giveback/no-follow-through supports
a specific hypothesis. No generic Position Manager rollout.

Initial diagnostic on the canonical XAU structural-displacement 1.5R replay:
- loss after favorable MFE is not stable across windows: 6/9 negative validation
  outcomes reached at least +0.5R MFE, versus 0/4 negative holdout outcomes;
- timeout is not the dominant defect: validation timeouts total +2.071R and
  holdout timeouts total +2.748R;
- opposite-direction M15 regime loss is too rare: 1 validation case, 0 holdout;
- extension beyond 1.5R is the only repeated symptom: 6/9 validation target
  winners and 5/7 holdout target winners reached at least 2.0R within the same
  12-M5 horizon.

Hypothesis 1 was therefore pre-registered before outcome replay:
`xau_sd_fixed_target_1_5r_vs_2r_exit_v1`. The champion cohort is frozen by the
canonical 1.5R overlap policy. Challenger and champion use identical signal,
entry, structural stop, sizing, costs and 12-M5 horizon; only fixed target R
changes from 1.5 to 2.0.

Result with actual MT4 DEMO equity and the frozen validation/holdout split:
- validation N=25: 1.5R +10.571R / exp +0.423R / PF 2.46 versus 2.0R
  +10.408R / exp +0.416R / PF 2.44; delta -0.163R;
- holdout N=14: 1.5R +9.248R / exp +0.661R / PF 3.31 versus 2.0R
  +8.272R / exp +0.591R / PF 2.65; delta -0.977R.

Conclusion: fixed 2.0R is rejected because it degrades both independent windows.
The canonical XAU structural-displacement champion remains fixed target 1.5R.
The negative result is retained in Research to avoid retesting it.
`authority_effect=false`; no PAPER/admission/broker/risk/sizing rule changes.

Hypothesis 2 is also complete and rejected:
`xau_sd_extend_2r_if_prior_3_m5_directional_v1` extends to 2.0R only when the
three prior fully closed M5 bars are strictly directional at the first 1.5R
touch. It qualified 4 validation and 3 holdout extensions, but degraded total R
by -1.954R and -1.500R respectively. Simple M5 target-event momentum is therefore
not a sufficient extension selector. Champion remains fixed 1.5R.

Current evidence also still rejects Position Manager V2 as a wholesale
replacement: validation and full-history performance degrade despite a holdout
improvement. Any next P2-B hypothesis must be conditional and causal, and must
be tested alone against the unchanged 1.5R champion.

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


P1-B operational cadence correction:
- the installed 05:43 daily cron invokes the admission refresh script in PREVIEW mode only;
- PREVIEW now reuses the same runtime service as the API, therefore sizing capital is actual MT4 DEMO equity first, DEMO balance fallback, never the research fallback;
- APPLY requires the explicit `--apply` flag and still fails closed unless drain is ON, Trading-New BOOK_FLAT is proven and all active symbols were evaluated.
