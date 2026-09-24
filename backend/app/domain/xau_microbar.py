from datetime import datetime

from pydantic import BaseModel, Field


class XauMicrobarM1(BaseModel):
    minute_at: datetime
    first_quote_at: datetime
    last_quote_at: datetime
    bid_open: float = Field(gt=0)
    bid_high: float = Field(gt=0)
    bid_low: float = Field(gt=0)
    bid_close: float = Field(gt=0)
    ask_open: float = Field(gt=0)
    ask_high: float = Field(gt=0)
    ask_low: float = Field(gt=0)
    ask_close: float = Field(gt=0)
    mid_open: float = Field(gt=0)
    mid_high: float = Field(gt=0)
    mid_low: float = Field(gt=0)
    mid_close: float = Field(gt=0)
    spread_open: float = Field(ge=0)
    spread_high: float = Field(ge=0)
    spread_low: float = Field(ge=0)
    spread_close: float = Field(ge=0)
    spread_sum: float = Field(ge=0)
    quote_count: int = Field(gt=0)

    @property
    def average_spread(self) -> float:
        return self.spread_sum / self.quote_count


class XauMicrobarState(BaseModel):
    started_at: datetime
    last_quote_at: datetime | None = None
    total_quote_samples: int = Field(default=0, ge=0)
    current_bar: XauMicrobarM1 | None = None


class XauMicrobarGeometry(BaseModel):
    window_minutes: int = Field(gt=0)
    bars: int = Field(gt=0)
    start_at: datetime
    end_at: datetime
    mid_open: float = Field(gt=0)
    mid_high: float = Field(gt=0)
    mid_low: float = Field(gt=0)
    mid_close: float = Field(gt=0)
    range_price: float = Field(ge=0)
    signed_move: float
    close_location: float = Field(ge=0, le=1)
    path_efficiency: float = Field(ge=0, le=1)
    average_spread: float = Field(ge=0)
    max_spread: float = Field(ge=0)
    average_quotes_per_bar: float = Field(ge=0)
    distance_to_low: float = Field(ge=0)
    distance_to_high: float = Field(ge=0)


class XauMicrobarSummary(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "M1"
    started_at: datetime | None = None
    healthy: bool = False
    quote_age_seconds: float | None = Field(default=None, ge=0)
    last_quote_at: datetime | None = None
    total_quote_samples: int = Field(default=0, ge=0)
    closed_bars: int = Field(default=0, ge=0)
    latest_closed_bar_at: datetime | None = None
    current_bar: XauMicrobarM1 | None = None
    geometry_5m: XauMicrobarGeometry | None = None
    geometry_15m: XauMicrobarGeometry | None = None
    recent: list[XauMicrobarM1] = Field(default_factory=list)
