from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MarketFeedStatus(StrEnum):
    LIVE = "live"
    STALE = "stale"


class LiveMarketQuote(BaseModel):
    symbol: str
    as_of: datetime
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    mid: float = Field(gt=0)
    spread: float = Field(ge=0)
    spread_pct: float = Field(ge=0)
    digits: int = Field(ge=0, le=12)
    age_seconds: float = Field(ge=0)
    status: MarketFeedStatus
    last_closed_m5_at: datetime | None = None
    recent_change_pct: float | None = None
    recent_m5_closes: list[float] = Field(default_factory=list)
