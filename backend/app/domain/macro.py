from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MacroImpact(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


class MacroSignalPhase(StrEnum):
    BLACKOUT = "blackout"
    POST_SAFE = "post_safe"
    NORMAL = "normal"


class MacroSignalContext(BaseModel):
    phase: MacroSignalPhase
    at: datetime
    event_id: str | None = None
    event_name: str | None = None
    event_start_at: datetime | None = None
    safe_resume_at: datetime | None = None
    minutes_from_safe_resume: float | None = None
    post_safe_window_minutes: int = Field(default=135, ge=0)


class MacroEvent(BaseModel):
    event_id: str
    name: str
    start_at: datetime
    end_at: datetime
    impact: MacroImpact
    currencies: list[str] = Field(default_factory=lambda: ["USD"])
    pre_block_minutes: int = Field(default=30, ge=0)
    post_block_minutes: int = Field(default=45, ge=0)
    source: str


class MacroGateStatus(BaseModel):
    at: datetime
    blocked: bool
    active_events: list[MacroEvent]
    next_event: MacroEvent | None = None
    reason: str
