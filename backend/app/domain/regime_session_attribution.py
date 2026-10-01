from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.regime import MarketRegime


class AttributionWindow(StrEnum):
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class AttributionDimension(StrEnum):
    SESSION = "session"
    REGIME = "regime"


class RegimeSessionAttributionBucket(BaseModel):
    window: AttributionWindow
    dimension: AttributionDimension
    key: str
    trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    total_r: float = 0.0
    expectancy_r: float | None = None
    profit_factor: float | None = None
    max_drawdown_r: float = Field(default=0.0, ge=0)
    average_execution_cost_r: float | None = None


class RegimeSessionAttributionReport(BaseModel):
    generated_at: datetime
    symbol: str
    strategy_id: str
    target_r: float
    capital_eur: float
    capital_source: str
    train_end: datetime
    validation_end: datetime
    validation_trades: int = Field(ge=0)
    holdout_trades: int = Field(ge=0)
    session_buckets: list[RegimeSessionAttributionBucket]
    regime_buckets: list[RegimeSessionAttributionBucket]
    session_partition: list[str]
    regime_partition: list[MarketRegime]
    authority_effect: bool = False
    limitations: list[str] = Field(default_factory=list)
