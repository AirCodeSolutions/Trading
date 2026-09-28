from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import StopGeometrySource


class StopGeometrySummary(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    source: StopGeometrySource
    total_instrumented: int = Field(ge=0)
    spread_blocked: int = Field(ge=0)
    executable: int = Field(ge=0)
    median_stop_atr_m5: float | None = None
    median_stop_atr_m15: float | None = None
    median_spread_atr_m5: float | None = None
    median_spread_atr_m15: float | None = None
    median_spread_to_stop: float | None = None
    median_additional_distance_atr_m5: float | None = None
    median_additional_distance_atr_m15: float | None = None
    blocked_wins: int = Field(ge=0)
    blocked_losses: int = Field(ge=0)
    blocked_total_r: float = 0.0
    blocked_expectancy_r: float = 0.0


class StopGeometryResearchReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    instrumented_observations: int = Field(ge=0)
    legacy_observations_excluded: int = Field(ge=0)
    summaries: list[StopGeometrySummary] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
