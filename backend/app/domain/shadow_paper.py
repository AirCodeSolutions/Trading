from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class PaperTradeStatus(StrEnum):
    OPEN = "open"
    STOP = "stop"
    TARGET = "target"
    TIMEOUT = "timeout"


class ShadowPaperTrade(BaseModel):
    trade_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    entry_bar_at: datetime
    opened_at: datetime
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    spread_at_entry: float = Field(ge=0)
    lots: float = Field(gt=0)
    risk_eur: float = Field(gt=0)
    risk_distance: float = Field(gt=0)
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    status: PaperTradeStatus = PaperTradeStatus.OPEN
    exit_at: datetime | None = None
    exit_price: float | None = None
    result_r: float | None = None
    pnl_eur: float | None = None
    bars_held: int = Field(default=0, ge=0)


class ShadowPaperState(BaseModel):
    last_started_signal_at: datetime | None = None
    open_trade: ShadowPaperTrade | None = None


class ShadowPaperSummary(BaseModel):
    closed_trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(default=0.0, ge=0)
    total_pnl_eur: float
    open_trade: ShadowPaperTrade | None = None
    recent_trades: list[ShadowPaperTrade] = Field(default_factory=list)
