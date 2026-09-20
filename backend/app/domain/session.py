from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SessionReadinessStatus(StrEnum):
    READY = "ready"
    WAITING_MARKET = "waiting_market"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class SessionAssetState(StrEnum):
    READY = "ready"
    WAITING_QUOTE = "waiting_quote"
    MISSING_SPEC = "missing_spec"
    MISSING_HISTORY = "missing_history"


class SessionAssetStatus(BaseModel):
    symbol: str
    state: SessionAssetState
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
    waiting_symbols: list[str]
    degraded_symbols: list[str]
    assets: list[SessionAssetStatus]
    reason: str
