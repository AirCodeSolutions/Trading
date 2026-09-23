from pydantic import BaseModel

from app.domain.admission import AdmissionDecision
from app.domain.opportunity import PerformanceSummary
from app.domain.opportunity_funnel import ResearchProbeQualification


class ProbeReviewPack(BaseModel):
    strategy_id: str
    review_ready: bool
    reason: str
    probe_qualification: ResearchProbeQualification | None = None
    historical_admission: AdmissionDecision | None = None
    train: PerformanceSummary | None = None
    validation: PerformanceSummary | None = None
    holdout: PerformanceSummary | None = None
    requires_human_decision: bool = True
