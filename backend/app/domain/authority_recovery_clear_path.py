from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ClearPathEvidenceState(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ECONOMICALLY_REJECTED = "economically_rejected"
    REVIEW_READY = "review_ready"


class ClearPathWindowMetrics(BaseModel):
    observations: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    flats: int = Field(ge=0)
    total_r: float
    expectancy_r: float | None = None
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)


class ClearPathRecoveryReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    hypothesis_id: str
    resolved_unqualified: int = Field(ge=0)
    context_available: int = Field(ge=0)
    selected_resolved: int = Field(ge=0)
    selection_rate: float = Field(ge=0, le=1)
    selected: ClearPathWindowMetrics
    older_half: ClearPathWindowMetrics
    recent_half: ClearPathWindowMetrics
    minimum_observations: int = Field(gt=0)
    required_additional_observations: int = Field(ge=0)
    evidence_state: ClearPathEvidenceState
    supports_demo: bool = False
    authority_effect: bool = False
    human_review_required: bool = True
    limitations: list[str] = Field(default_factory=list)
