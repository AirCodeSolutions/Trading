from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism


class AuthorityDecision(StrEnum):
    PAPER_ACCEPTED = "paper_accepted"
    BROKER_DEMO_EXECUTED = "broker_demo_executed"
    AUTHORITY_REJECTED = "authority_rejected"
    ECONOMIC_GUARD_BLOCKED = "economic_guard_blocked"


class AuthorityOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    FLAT = "flat"


class AuthorityRegretObservation(BaseModel):
    observation_id: str
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    signal_at: datetime
    decision: AuthorityDecision
    reason: str
    outcome: AuthorityOutcome
    result_r: float
    spread_cost_r: float | None = None
    broker_cost_adjusted_r: float | None = None
    broker_cost_adjustment_complete: bool = False


class AuthorityRegretBucket(BaseModel):
    key: str
    observations: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    flats: int = Field(ge=0)
    total_r: float
    expectancy_r: float | None = None
    positive_r: float = 0.0
    negative_r: float = 0.0
    broker_cost_adjusted_total_r: float | None = None
    broker_cost_adjustment_complete: bool = False


class AuthorityRegretReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime

    accepted_resolved: int = Field(ge=0)
    accepted_winners: int = Field(ge=0)
    accepted_losers: int = Field(ge=0)
    accepted_total_r: float

    broker_executed_resolved: int = Field(ge=0)
    broker_executed_winners: int = Field(ge=0)
    broker_executed_losers: int = Field(ge=0)
    broker_executed_total_r: float

    authority_rejected_resolved: int = Field(ge=0)
    winners_missed: int = Field(ge=0)
    winners_missed_r: float
    losses_avoided: int = Field(ge=0)
    losses_avoided_r: float
    rejected_counterfactual_total_r: float

    guard_blocked_resolved: int = Field(ge=0)
    guard_blocked_winners: int = Field(ge=0)
    guard_blocked_losses: int = Field(ge=0)
    guard_blocked_total_r: float

    by_reason: list[AuthorityRegretBucket] = Field(default_factory=list)
    by_strategy: list[AuthorityRegretBucket] = Field(default_factory=list)
    recent: list[AuthorityRegretObservation] = Field(default_factory=list)

    cost_basis: str
    limitations: list[str] = Field(default_factory=list)
