from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.market import Timeframe


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class DecisionAction(StrEnum):
    ENTER = "enter"
    EXIT = "exit"
    HOLD = "hold"
    REJECT = "reject"


class TradeDecision(BaseModel):
    symbol: str
    timeframe: Timeframe
    action: DecisionAction
    side: Side | None = None
    at: datetime
    reason: str
    strategy_id: str
    score: float | None = Field(default=None, ge=0, le=1)


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    max_loss_amount: float | None = Field(default=None, ge=0)
    position_size: float | None = Field(default=None, ge=0)
