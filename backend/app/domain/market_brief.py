from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.macro import MacroEvent


class MarketBriefAsset(BaseModel):
    symbol: str
    as_of: datetime
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    spread_atr_m5: float | None = None
    spread_atr_m15: float | None = None
    session: str | None = None
    market_session_state: str
    regime: str | None = None
    regime_direction: int | None = None
    volatility_percentile: float | None = None
    atr_m5: float | None = None
    atr_m15: float | None = None
    previous_day_high: float | None = None
    previous_day_low: float | None = None
    asia_high: float | None = None
    asia_low: float | None = None
    london_high_so_far: float | None = None
    london_low_so_far: float | None = None
    us_high_so_far: float | None = None
    us_low_so_far: float | None = None
    nearest_landmark: str | None = None
    nearest_landmark_price: float | None = None
    nearest_distance: float | None = None
    nearest_distance_atr_m5: float | None = None
    nearest_distance_atr_m15: float | None = None
    active_session_range_position: float | None = None
    next_event: MacroEvent | None = None
    next_event_time_until_minutes: float | None = None
    next_event_time_until_display: str | None = None
    next_event_relevance: str | None = None
    macro_blocked: bool = False
    readiness: str
    quote_age_seconds: float | None = None
    m5_age_minutes: float | None = None
    research_status: str = "observability active"
    warnings: list[str] = Field(default_factory=list)


class MarketBriefEvent(BaseModel):
    event: MacroEvent
    time_until_minutes: float
    time_until_display: str
    affected_assets: list[str] = Field(default_factory=list)
    macro_blocked_now: bool = False


class DailyMarketBrief(BaseModel):
    generated_at: datetime
    timezone: str
    assets: list[MarketBriefAsset] = Field(default_factory=list)
    upcoming_events: list[MarketBriefEvent] = Field(default_factory=list)
    global_warnings: list[str] = Field(default_factory=list)
    data_freshness: dict[str, object] = Field(default_factory=dict)
