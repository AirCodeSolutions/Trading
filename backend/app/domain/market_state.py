from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.session_landmark import SessionLandmarkContext


class MarketStateFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class MarketStateM1Context(BaseModel):
    available: bool = False
    source: str = "unavailable"
    at: datetime | None = None
    pressure: float | None = None
    direction: int | None = None
    freshness_seconds: float | None = None


class MarketStateQuoteContext(BaseModel):
    available: bool = False
    as_of: datetime | None = None
    status: str = "unavailable"
    age_seconds: float | None = None
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None


class MarketStateMacroContext(BaseModel):
    available: bool = False
    source: str = "unavailable"
    blocked: bool | None = None
    next_event_name: str | None = None


class MarketStateV2(BaseModel):
    symbol: str
    evaluated_at: datetime
    latest_closed_m5_at: datetime | None = None  # source bar start, retained for compatibility
    latest_closed_m15_at: datetime | None = None  # source bar start, retained for compatibility
    latest_m5_bar_at: datetime | None = None
    latest_m5_closed_at: datetime | None = None
    latest_m15_bar_at: datetime | None = None
    latest_m15_closed_at: datetime | None = None
    m5_freshness: MarketStateFreshness
    m15_freshness: MarketStateFreshness
    regime: str | None = None
    regime_direction: int | None = None
    regime_confidence: float | None = None
    atr_m15: float | None = None
    atr_ratio_m15: float | None = None
    efficiency_m15: float | None = None
    atr_m5: float | None = None
    m5_direction: int | None = None
    persistence: float | None = None
    persistence_magnitude: float | None = None
    momentum_atr: float | None = None
    acceleration_atr: float | None = None
    efficiency_m5: float | None = None
    extension_atr: float | None = None
    distance_to_recent_structure_atr: float | None = None
    range_expansion_ratio: float | None = None
    exhaustion_proxy: float | None = None
    session_context: SessionLandmarkContext | None = None
    macro: MarketStateMacroContext = Field(default_factory=MarketStateMacroContext)
    quote: MarketStateQuoteContext = Field(default_factory=MarketStateQuoteContext)
    spread: float | None = None
    spread_atr_m5: float | None = None
    spread_atr_m15: float | None = None
    m1: MarketStateM1Context = Field(default_factory=MarketStateM1Context)
