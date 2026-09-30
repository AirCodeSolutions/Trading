from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class OpportunityState(StrEnum):
    NONE = "none"
    SETUP = "setup"
    ARMED = "armed"
    TRIGGERED = "triggered"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class OpportunityStateEvent(StrEnum):
    SETUP_DETECTED = "setup_detected"
    ARMED = "armed"
    TRIGGERED = "triggered"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class OpportunityStateTransition(BaseModel):
    state: OpportunityState
    at: datetime
    source_closed_at: datetime
    event: OpportunityStateEvent
    reason: str


class OpportunityStateSnapshot(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    side: Side | None = None
    state: OpportunityState
    first_seen_at: datetime | None = None
    updated_at: datetime
    triggered_at: datetime | None = None
    invalidation_reason: str | None = None
    expiration_reason: str | None = None
    reason: str
    provenance: list[OpportunityStateTransition] = Field(default_factory=list)

    @computed_field
    @property
    def age_seconds(self) -> float | None:
        if self.first_seen_at is None:
            return None
        return max(0.0, (self.updated_at - self.first_seen_at).total_seconds())
