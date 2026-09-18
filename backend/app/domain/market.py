from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Timeframe(StrEnum):
    M5 = "M5"
    M15 = "M15"


class MarketBar(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: Timeframe
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "MarketBar":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, close and high")
        return self
