from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.broker import PositionSizeResult
from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class ManualDemoTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: Side
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    risk_fraction: float = Field(default=0.01, gt=0, le=1)


class ManualDemoSubmitRequest(ManualDemoTradeRequest):
    confirmed: bool = False


class ManualDemoOpportunityRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    mechanism: OpportunityMechanism


class ManualDemoTradePreview(BaseModel):
    at: datetime
    symbol: str
    side: Side
    bid: float
    ask: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_fraction: float
    reward_distance: float
    reward_risk_ratio: float
    quote_age_seconds: float
    remaining_daily_loss_budget_eur: float
    approved: bool
    reasons: list[str]
    sizing: PositionSizeResult | None = None
