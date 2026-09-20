from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.approval import ProposalStatus
from app.domain.portfolio import PortfolioAction
from app.domain.trading import Side


class DemoBridgeCommandStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FILLED = "filled"
    REFUSED = "refused"
    ERROR = "error"


class DemoExecutionGuard(BaseModel):
    at: datetime
    ready: bool
    execution_mode: str
    bridge_enabled: bool
    live_trading_enabled: bool
    broker_is_demo: bool
    portfolio_action: PortfolioAction
    macro_blocked: bool
    reasons: list[str]


class DemoOrderCommand(BaseModel):
    command_id: str
    symbol: str
    side: Side
    lots: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    strategy_id: str
    issued_at: datetime
    magic_number: int
    slippage_points: int = Field(ge=0)
    proposal_status: ProposalStatus


class DemoBridgeResult(BaseModel):
    command_id: str
    status: DemoBridgeCommandStatus
    ticket: int = 0
    error_code: int = 0
    fill_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    processed_at: str = ""


class DemoBridgePosition(BaseModel):
    ticket: int
    symbol: str
    side: Side
    lots: float
    open_price: float
    stop_loss: float
    take_profit: float
    profit: float
    open_time: str
    strategy_comment: str


class DemoExecutionStatus(BaseModel):
    guard: DemoExecutionGuard
    pending_command: DemoOrderCommand | None = None
    latest_result: DemoBridgeResult | None = None
    bridge_positions: list[DemoBridgePosition] = Field(default_factory=list)
