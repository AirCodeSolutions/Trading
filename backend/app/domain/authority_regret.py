from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.admission import AdmissionState
from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import ProspectiveQualificationState
from app.domain.shadow_paper import ShadowPaperTrade


class StrategyAuthorityDecision(StrEnum):
    BROKER_DEMO_ALLOWED = "broker_demo_allowed"
    BROKER_DEMO_LOCKED = "broker_demo_locked"


class AuthorityRegretOutcome(StrEnum):
    AUTHORIZED_WINNER = "authorized_winner"
    AUTHORIZED_LOSER = "authorized_loser"
    LOCKED_WINNER_MISSED = "locked_winner_missed"
    LOCKED_LOSS_AVOIDED = "locked_loss_avoided"
    FLAT = "flat"


class StrategyAuthoritySnapshot(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    signal_at: datetime
    historical_state: AdmissionState | None = None
    prospective_state: ProspectiveQualificationState
    paper_entry_allowed: bool
    decision: StrategyAuthorityDecision
    reason: str
class AuthorityRegretOpen(BaseModel):
    authority: StrategyAuthoritySnapshot
    trade: ShadowPaperTrade


class AuthorityRegretState(BaseModel):
    last_started_signal_at: datetime | None = None
    open_records: list[AuthorityRegretOpen] = Field(default_factory=list)


class AuthorityRegretRecord(BaseModel):
    authority: StrategyAuthoritySnapshot
    trade: ShadowPaperTrade
    outcome: AuthorityRegretOutcome


class AuthorityRegretReasonSummary(BaseModel):
    reason: str
    resolved: int = Field(ge=0)
    total_r: float = 0.0
    winners: int = Field(ge=0)
    losers: int = Field(ge=0)


class AuthorityRegretSummary(BaseModel):
    resolved: int = Field(ge=0)
    open_trades: int = Field(ge=0)
    authorized_winners: int = Field(ge=0)
    authorized_losers: int = Field(ge=0)
    locked_winners_missed: int = Field(ge=0)
    locked_losses_avoided: int = Field(ge=0)
    authorized_total_r: float = 0.0
    locked_counterfactual_total_r: float = 0.0
    missed_winner_r: float = 0.0
    avoided_loss_r: float = 0.0
    net_authority_regret_r: float = 0.0
    by_reason: list[AuthorityRegretReasonSummary] = Field(default_factory=list)
    recent: list[AuthorityRegretRecord] = Field(default_factory=list)
    broker_authority_changed: bool = False
