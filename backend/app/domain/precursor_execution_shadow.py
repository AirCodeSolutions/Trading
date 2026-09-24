from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.opportunity import TradeOutcome


class PrecursorExecutionShadowState(BaseModel):
    started_at: datetime


class PrecursorExecutionShadowRow(BaseModel):
    precursor_id: str
    first_seen_at: datetime
    outcome: TradeOutcome


class PrecursorExecutionShadowSummary(BaseModel):
    strategy_id: str
    started_at: datetime | None = None
    resolved: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    total_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = Field(default=0.0, ge=0)
    max_drawdown_r: float = Field(default=0.0, ge=0)
    recent: list[PrecursorExecutionShadowRow] = Field(default_factory=list)
