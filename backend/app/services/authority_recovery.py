from datetime import datetime, timedelta
from pathlib import Path

from app.domain.authority_recovery import (
    AuthorityRecoveryEvidenceState,
    AuthorityRecoveryReport,
)
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import ShadowPaperTrade
from app.services.shadow_paper import load_closed_trades

HYPOTHESIS_ID = "recover_rejected_xau_structural_displacement_1_5r_v1"
STRATEGY_ID = "XAUUSD:structural_displacement_sequence"
MIN_OBSERVATIONS = 20


def _resolved_unqualified_rows(runtime_dir: Path) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        rows.extend(load_closed_trades(path))
    return rows


def _profit_factor(values: list[float]) -> float:
    gains = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    return gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)


def _drawdown(values: list[float]) -> float:
    equity = peak = maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def build_authority_recovery_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
) -> AuthorityRecoveryReport:
    if window_hours < 1 or window_hours > 168:
        raise ValueError("window_hours must be between 1 and 168")
    start = now - timedelta(hours=window_hours)
    rows = [
        row
        for row in _resolved_unqualified_rows(runtime_dir)
        if row.symbol.upper() == "XAUUSD"
        and row.mechanism is OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
        and row.result_r is not None
        and start <= row.signal_at <= now
    ]
    rows.sort(key=lambda row: (row.signal_at, row.trade_id))
    values = [float(row.result_r) for row in rows if row.result_r is not None]
    count = len(values)
    state = (
        AuthorityRecoveryEvidenceState.REVIEW_READY
        if count >= MIN_OBSERVATIONS
        else AuthorityRecoveryEvidenceState.INSUFFICIENT_EVIDENCE
    )
    return AuthorityRecoveryReport(
        generated_at=now,
        window_hours=window_hours,
        hypothesis_id=HYPOTHESIS_ID,
        strategy_id=STRATEGY_ID,
        candidate_resolved=count,
        wins=sum(v > 0 for v in values),
        losses=sum(v < 0 for v in values),
        flats=sum(v == 0 for v in values),
        candidate_total_r=sum(values),
        expectancy_r=(sum(values) / count if count else None),
        profit_factor=_profit_factor(values),
        max_drawdown_r=_drawdown(values),
        minimum_observations=MIN_OBSERVATIONS,
        required_additional_observations=max(0, MIN_OBSERVATIONS - count),
        evidence_state=state,
        supports_demo=False,
        authority_effect=False,
        human_review_required=True,
        limitations=[
            "This cohort contains only executable unqualified probes already rejected from PAPER authority.",
            "The family filter is pre-registered from prior independent XAU structural-displacement evidence, not fitted on these probe outcomes.",
            "Twenty resolved prospective observations are required before review-ready status.",
            "Review-ready is not SUPPORTS_DEMO and cannot grant broker authority automatically.",
        ],
    )
