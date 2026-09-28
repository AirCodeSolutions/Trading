from datetime import datetime

from pydantic import BaseModel, Field


class SessionLandmarkSummary(BaseModel):
    symbol: str
    mechanism: str
    population: str = "diagnostic"
    observable: int = Field(ge=0)
    winners: int = Field(ge=0)
    losers: int = Field(ge=0)
    median_nearest_distance_atr_m5: float | None = None
    median_nearest_distance_atr_m15: float | None = None
    median_active_session_position: float | None = None


class SessionLandmarkLatest(BaseModel):
    symbol: str
    mechanism: str
    context: dict[str, object]


class SessionLandmarkResearchReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    instrumented_observations: int = Field(ge=0)
    legacy_observations_excluded: int = Field(ge=0)
    summaries: list[SessionLandmarkSummary] = Field(default_factory=list)
    latest: list[SessionLandmarkLatest] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
