from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.portfolio import ProspectiveQualificationState


class QualificationHistoryEvent(BaseModel):
    at: datetime
    strategy_id: str
    state: ProspectiveQualificationState
    closed_trades: int = Field(ge=0)
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)
    reason: str
