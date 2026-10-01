from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity_funnel import (
    ResearchProbeQualification,
    ResearchProbeQualificationState,
)
from app.domain.portfolio import ProspectiveQualificationState
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperSummary, ShadowPaperTrade
from app.services.admission import paper_entry_allowed
from app.services.prospective_qualification import (
    MIN_PROSPECTIVE_TRADES,
    assess_prospective,
)
from app.services.shadow_paper import load_closed_trades, load_shadow_paper_state


def assess_research_probe_evidence(
    strategy_id: str,
    probes: Sequence[ShadowPaperTrade],
) -> ResearchProbeQualification | None:
    closed = sorted(
        (
            probe
            for probe in probes
            if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
        ),
        key=lambda probe: probe.signal_at,
    )
    open_probe = next(
        (probe for probe in probes if probe.status == PaperTradeStatus.OPEN),
        None,
    )
    if not closed and open_probe is None:
        return None

    results = [probe.result_r for probe in closed if probe.result_r is not None]
    gains = sum(result for result in results if result > 0)
    losses = -sum(result for result in results if result < 0)
    profit_factor = gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for result in results:
        equity += result
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    summary = ShadowPaperSummary(
        closed_trades=len(closed),
        wins=sum(result > 0 for result in results),
        losses=sum(result < 0 for result in results),
        total_r=sum(results),
        expectancy_r=(sum(results) / len(results)) if results else 0.0,
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        total_pnl_eur=sum(probe.pnl_eur or 0.0 for probe in closed),
        open_trade=open_probe,
    )
    qualification = assess_prospective(strategy_id, summary)
    state = {
        ProspectiveQualificationState.COLLECTING: ResearchProbeQualificationState.COLLECTING,
        ProspectiveQualificationState.FAILED: ResearchProbeQualificationState.FAILED,
        ProspectiveQualificationState.SUPPORTS_DEMO: ResearchProbeQualificationState.SUPPORTS_REVIEW,
    }[qualification.state]

    if state == ResearchProbeQualificationState.COLLECTING:
        reason = (
            f"{qualification.closed_trades}/{MIN_PROSPECTIVE_TRADES} resolved "
            "executable probes; minimum research-review sample not reached"
        )
    elif state == ResearchProbeQualificationState.FAILED:
        reason = qualification.reason.replace(
            "prospective ",
            "prospective executable-probe ",
            1,
        )
    else:
        reason = (
            "prospective executable-probe evidence meets the existing paper "
            "thresholds; SHADOW may start PAPER evidence but gains no broker authority"
        )

    return ResearchProbeQualification(
        state=state,
        closed_trades=qualification.closed_trades,
        minimum_trades=MIN_PROSPECTIVE_TRADES,
        expectancy_r=qualification.expectancy_r,
        profit_factor=qualification.profit_factor,
        max_drawdown_r=qualification.max_drawdown_r,
        reason=reason,
    )


def load_research_probe_qualification(
    runtime_dir: Path,
    *,
    prefix: str,
    strategy_id: str,
) -> ResearchProbeQualification | None:
    probes = list(
        load_closed_trades(runtime_dir / f"{prefix}_unqualified_probes.jsonl")
    )
    open_probe = load_shadow_paper_state(
        runtime_dir / f"{prefix}_unqualified_probe_state.json"
    ).open_trade
    if open_probe is not None:
        probes.append(open_probe)
    return assess_research_probe_evidence(strategy_id, probes)


def probe_supports_paper(
    admission: AdmissionDecision | None,
    qualification: ResearchProbeQualification | None,
) -> bool:
    return (
        admission is not None
        and admission.state == AdmissionState.SHADOW
        and qualification is not None
        and qualification.state == ResearchProbeQualificationState.SUPPORTS_REVIEW
    )


def paper_entry_allowed_with_probe_evidence(
    admission: AdmissionDecision | None,
    qualification: ResearchProbeQualification | None,
) -> bool:
    return paper_entry_allowed(admission) or probe_supports_paper(
        admission,
        qualification,
    )
