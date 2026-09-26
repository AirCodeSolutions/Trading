from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SessionReadinessStatus(StrEnum):
    READY = "ready"
    WARMING_UP = "warming_up"
    WAITING_MARKET = "waiting_market"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class SessionAssetState(StrEnum):
    READY = "ready"
    MARKET_CLOSED = "market_closed"
    UNKNOWN_SESSION = "unknown_session"
    WARMING_UP = "warming_up"
    WAITING_QUOTE = "waiting_quote"
    M5_STALLED = "m5_stalled"
    MISSING_SPEC = "missing_spec"
    MISSING_HISTORY = "missing_history"


class SessionAssetTimeline(BaseModel):
    symbol: str
    quote_live_since: datetime | None = None
    first_fresh_m5_at: datetime | None = None
    ready_at: datetime | None = None
    m5_stalled_at: datetime | None = None
    last_closed_m5_at: datetime | None = None


class SessionRuntimeSymbolState(BaseModel):
    quote_live_since: datetime | None = None
    first_fresh_m5_at: datetime | None = None
    ready_at: datetime | None = None
    m5_stalled_at: datetime | None = None


class SessionRuntimeState(BaseModel):
    symbols: dict[str, SessionRuntimeSymbolState] = Field(default_factory=dict)


class SessionAssetStatus(BaseModel):
    symbol: str
    state: SessionAssetState
    market_session: str
    quote_live: bool
    paper_ready: bool
    broker_spec_ready: bool
    has_m5: bool
    has_m15: bool
    price: float = Field(gt=0)
    as_of: datetime
    reason: str


class ShadowWorkerHeartbeat(BaseModel):
    at: datetime
    ok: bool
    cost_samples_appended: int = Field(ge=0)
    shadow_scans: int = Field(ge=0)
    signals: int = Field(ge=0)
    paper_ready_symbols: list[str]
    warming_up_symbols: list[str] = Field(default_factory=list)
    error: str | None = None


class SessionPreflight(BaseModel):
    at: datetime
    status: SessionReadinessStatus
    worker_ok: bool
    worker_age_seconds: float | None = Field(default=None, ge=0)
    macro_blocked: bool
    portfolio_action: str
    demo_execution_ready: bool
    ready_symbols: list[str]
    warming_symbols: list[str]
    waiting_symbols: list[str]
    closed_symbols: list[str] = Field(default_factory=list)
    degraded_symbols: list[str]
    assets: list[SessionAssetStatus]
    timeline: list[SessionAssetTimeline] = Field(default_factory=list)
    reason: str
