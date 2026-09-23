from datetime import datetime

from pydantic import BaseModel, Field


class TrailingShadowState(BaseModel):
    started_at: datetime


class TrailingShadowEvaluation(BaseModel):
    trade_id: str
    evaluated_at: datetime
    static_result_r: float
    trailing_result_r: float
    delta_r: float
    static_pnl_eur: float
    trailing_pnl_eur: float
    adjustments: int = Field(ge=0)
    exit_reason: str


class TrailingShadowSummary(BaseModel):
    strategy_id: str
    started_at: datetime | None = None
    resolved: int = Field(ge=0)
    improved: int = Field(ge=0)
    worsened: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    static_total_r: float = 0.0
    trailing_total_r: float = 0.0
    expectancy_delta_r: float = 0.0
    total_adjustments: int = Field(default=0, ge=0)
    recent: list[TrailingShadowEvaluation] = Field(default_factory=list)
