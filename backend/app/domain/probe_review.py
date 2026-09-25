from pydantic import BaseModel, Field

from app.domain.admission import AdmissionDecision
from app.domain.opportunity import PerformanceSummary
from app.domain.opportunity_funnel import ResearchProbeQualification
from app.domain.trading_intelligence import (
    AdmittedTradeEarlyContextSummary,
    BlockedProbeEarlyContextSummary,
    OpportunityWaitingSummary,
    ProbeEarlyContextSummary,
    WaitingEarlyContextSummary,
)


class ProbeReviewPack(BaseModel):
    strategy_id: str
    review_ready: bool
    reason: str
    probe_qualification: ResearchProbeQualification | None = None
    historical_admission: AdmissionDecision | None = None
    train: PerformanceSummary | None = None
    validation: PerformanceSummary | None = None
    holdout: PerformanceSummary | None = None
    evidence_window_hours: int | None = None
    prospective_probe_context: ProbeEarlyContextSummary | None = None
    waiting_cost_context: OpportunityWaitingSummary | None = None
    waiting_early_context: WaitingEarlyContextSummary | None = None
    admitted_trade_context: AdmittedTradeEarlyContextSummary | None = None
    blocked_probe_contexts: list[BlockedProbeEarlyContextSummary] = Field(
        default_factory=list
    )
    requires_human_decision: bool = True
