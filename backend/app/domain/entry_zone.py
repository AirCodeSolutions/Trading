from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.domain.opportunity_state import OpportunityState
from app.domain.trading import Side


class EntryZoneState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    DATA_UNAVAILABLE = "data_unavailable"
    WAITING_PRICE = "waiting_price"
    CURRENTLY_EXECUTABLE = "currently_executable"
    ECONOMICALLY_BLOCKED = "economically_blocked"


class EntryZoneSizing(BaseModel):
    capital_source: str
    risk_budget_eur: float | None = None
    lots: float | None = None
    expected_loss_eur: float | None = None
    min_lot_loss_eur: float | None = None
    estimated_margin_eur: float | None = None
    sizing_reason: str | None = None


class ExecutableEntryZoneV2(BaseModel):
    symbol: str
    mechanism: str
    side: Side | None = None
    opportunity_state: OpportunityState
    state: EntryZoneState
    trigger_at: datetime | None = None
    trigger_source_closed_at: datetime | None = None
    evaluated_at: datetime
    current_entry: float | None = None
    structural_stop: float | None = None
    current_stop_distance: float | None = None
    minimum_stop_distance_for_spread: float | None = None
    maximum_stop_distance_for_min_lot_budget: float | None = None
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    spread: float | None = None
    spread_to_stop: float | None = None
    sizing: EntryZoneSizing | None = None
    post_trigger_chase_atr: float | None = None
    extension_atr: float | None = None
    momentum_atr: float | None = None
    acceleration_atr: float | None = None
    efficiency_m5: float | None = None
    range_expansion_ratio: float | None = None
    exhaustion_proxy: float | None = None
    favorable_landmark_type: str | None = None
    favorable_landmark_price: float | None = None
    favorable_landmark_distance: float | None = None
    favorable_landmark_distance_atr_m5: float | None = None
    room_to_landmark_r: float | None = None
    macro_available: bool = False
    macro_blocked: bool | None = None
    reason: str
