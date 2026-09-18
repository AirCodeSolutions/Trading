from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.market import Timeframe
from app.domain.trading import Side


class DecisionMode(StrEnum):
    AUTO = "auto"
    CONFIRM = "confirm"


class ProposalStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    AUTHORIZED = "authorized"
    DECLINED = "declined"


class ExecutionProposalRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Timeframe
    side: Side
    strategy_id: str
    at: datetime
    reason: str


class ExecutionProposal(BaseModel):
    id: str
    symbol: str
    timeframe: Timeframe
    side: Side
    strategy_id: str
    at: datetime
    reason: str
    status: ProposalStatus
