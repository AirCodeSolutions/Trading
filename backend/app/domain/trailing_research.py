from pydantic import BaseModel, Field

from app.domain.opportunity import (
    OpportunityMechanism,
    PerformanceSummary,
)
from app.domain.trailing_manager import TrailingManagerConfig


class TrailingComparisonWindow(BaseModel):
    static: PerformanceSummary
    treatment: PerformanceSummary
    paired_trades: int = Field(ge=0)
    improved_trades: int = Field(ge=0)
    worsened_trades: int = Field(ge=0)
    unchanged_trades: int = Field(ge=0)
    total_adjustments: int = Field(ge=0)
    expectancy_delta_r: float
    max_drawdown_delta_r: float


class TrailingResearchReport(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    policy: TrailingManagerConfig
    candidates: int = Field(ge=0)
    paired_executed: int = Field(ge=0)
    rejected: int = Field(ge=0)
    rejection_reasons: dict[str, int]
    train: TrailingComparisonWindow
    validation: TrailingComparisonWindow
    holdout: TrailingComparisonWindow
    no_added_risk_violations: int = Field(default=0, ge=0)
