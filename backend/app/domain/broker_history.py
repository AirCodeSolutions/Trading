from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading import Side


class BrokerClosedTrade(BaseModel):
    ticket: int = Field(gt=0)
    symbol: str
    side: Side
    lots: float = Field(gt=0)
    open_price: float = Field(gt=0)
    close_price: float = Field(gt=0)
    stop_loss: float = Field(ge=0)
    take_profit: float = Field(ge=0)
    profit_eur: float
    open_at: datetime
    close_at: datetime
    magic_number: int
    comment: str = ""


class BrokerClosedSummary(BaseModel):
    trades: int = Field(ge=0)
    realized_pnl_eur: float
    complete: bool = True
    missing_tickets: list[int] = Field(default_factory=list)
    closed_trades: list[BrokerClosedTrade] = Field(default_factory=list)
