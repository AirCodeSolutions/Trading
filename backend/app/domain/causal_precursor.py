from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)


class CausalPrecursorObservation(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    first_seen_at: datetime
    latest_closed_m5_at: datetime
    pattern: OpportunityCausalPattern
    side: Side
    context: OpportunityCausalContext


class CausalPrecursorCollectionState(BaseModel):
    started_at: datetime
