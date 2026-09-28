from datetime import datetime

from pydantic import BaseModel


class SessionLandmarkContext(BaseModel):
    """Causal, research-only session levels captured at a signal."""

    at: datetime
    active_session: str | None = None
    previous_day_high: float | None = None
    previous_day_low: float | None = None
    asia_high: float | None = None
    asia_low: float | None = None
    london_high_so_far: float | None = None
    london_low_so_far: float | None = None
    us_high_so_far: float | None = None
    us_low_so_far: float | None = None
    nearest_landmark_type: str | None = None
    nearest_landmark_price: float | None = None
    nearest_landmark_distance: float | None = None
    nearest_landmark_distance_atr_m5: float | None = None
    nearest_landmark_distance_atr_m15: float | None = None
    side_aligned_distance_to_nearest_landmark: float | None = None
    active_session_high: float | None = None
    active_session_low: float | None = None
    active_session_range: float | None = None
    active_session_range_atr_m5: float | None = None
    active_session_position: float | None = None
