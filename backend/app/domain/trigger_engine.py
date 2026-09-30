from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import OpportunityState
from app.domain.trading import Side


class TriggerEngineState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    M1_UNAVAILABLE = "m1_unavailable"
    WAITING = "waiting"
    EARLY_TRIGGERED = "early_triggered"
    V1_TRIGGERED = "v1_triggered"


class TriggerEngineV2Snapshot(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    side: Side | None = None
    opportunity_state: OpportunityState
    state: TriggerEngineState
    evaluated_at: datetime
    armed_at: datetime | None = None
    armed_source_closed_at: datetime | None = None
    early_trigger_at: datetime | None = None
    early_trigger_source_closed_at: datetime | None = None
    early_trigger_price: float | None = None
    early_trigger_source: str | None = None
    v1_trigger_at: datetime | None = None
    v1_trigger_source_closed_at: datetime | None = None
    v1_reference_price: float | None = None
    lead_seconds: float | None = None
    lead_minutes: float | None = None
    move_saved_vs_v1_atr: float | None = None
    m1_available: bool = False
    m1_status: str = "unavailable"
    latest_closed_m1_at: datetime | None = None
    latest_closed_m1_closed_at: datetime | None = None
    directional_tick_samples: int | None = None
    raw_tick_imbalance: float | None = None
    side_aligned_tick_imbalance: float | None = None
    m1_signed_move: float | None = None
    m1_close_location: float | None = None
    m1_average_spread: float | None = None
    reason: str

