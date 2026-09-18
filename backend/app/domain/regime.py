from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MarketRegime(StrEnum):
    WARMUP = "warmup"
    DEAD = "dead"
    BALANCED = "balanced_auction"
    DIRECTIONAL = "directional_expansion"
    POST_SHOCK = "post_shock"


class RegimeSnapshot(BaseModel):
    symbol: str
    at: datetime
    regime: MarketRegime
    direction: int = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    atr: float = Field(ge=0)
    atr_ratio: float = Field(ge=0)
    efficiency: float = Field(ge=0, le=1)
    shock_ratio: float = Field(ge=0)
    reason: str
