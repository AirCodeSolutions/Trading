from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AuthorityRecoveryEvidenceState(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REVIEW_READY = "review_ready"


class AuthorityRecoveryReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    hypothesis_id: str
    strategy_id: str
    candidate_resolved: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    flats: int = Field(ge=0)
    candidate_total_r: float
    expectancy_r: float | None = None
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)
    minimum_observations: int = Field(gt=0)
    required_additional_observations: int = Field(ge=0)
    evidence_state: AuthorityRecoveryEvidenceState
    supports_demo: bool = False
    authority_effect: bool = False
    human_review_required: bool = True
    limitations: list[str] = Field(default_factory=list)
