from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.macro import MacroGateStatus
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


class MarketStateV2(BaseModel):
    symbol: str
    evaluated_at: datetime
    latest_closed_m5_at: datetime | None = None
    latest_closed_m15_at: datetime | None = None
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
    macro: MacroGateStatus | None = None
    spread: float | None = None
    spread_atr_m5: float | None = None
    spread_atr_m15: float | None = None
    m1: MarketStateM1Context = Field(default_factory=MarketStateM1Context)
