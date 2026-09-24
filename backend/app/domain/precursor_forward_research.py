from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern


class PrecursorForwardOutcome(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    pattern: OpportunityCausalPattern
    side: Side
    first_seen_at: datetime
    horizon_end_at: datetime
    atr_m5: float = Field(gt=0)
    favorable_mfe_atr: float = Field(ge=0)
    adverse_mae_atr: float = Field(ge=0)
    signed_close_return_atr: float
    favorable_dominates: bool
    close_aligned: bool


class PrecursorForwardSummary(BaseModel):
    label: str
    raw_resolved: int = Field(ge=0)
    independent_resolved: int = Field(ge=0)
    average_favorable_mfe_atr: float = Field(ge=0)
    average_adverse_mae_atr: float = Field(ge=0)
    average_signed_close_return_atr: float
    favorable_dominance_rate: float = Field(ge=0, le=1)
    close_alignment_rate: float = Field(ge=0, le=1)


class PrecursorForwardResearchReport(BaseModel):
    generated_at: datetime
    prospective_started_at: datetime | None = None
    horizon_bars: int = Field(gt=0)
    raw_resolved: int = Field(ge=0)
    independent_resolved: int = Field(ge=0)
    pending: int = Field(ge=0)
    overall: PrecursorForwardSummary
    by_pattern: list[PrecursorForwardSummary] = Field(default_factory=list)
    by_symbol: list[PrecursorForwardSummary] = Field(default_factory=list)
    recent_independent: list[PrecursorForwardOutcome] = Field(default_factory=list)
