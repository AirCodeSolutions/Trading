from collections.abc import Sequence
from datetime import datetime, time, timedelta

from app.domain.market import MarketBar
from app.domain.session_landmark import SessionLandmarkContext, SessionLandmarkLocation
from app.domain.trading import Side
from app.services.mt4_csv import _server_timezone
from app.services.opportunity_strategies import (
    ASIA_RANGE_END_HOUR,
    ASIA_RANGE_START_HOUR,
)

_LONDON_START = time(10, 0)
_LONDON_END = time(18, 0)
_US_START = time(15, 30)
_US_END = time(22, 0)
_LANDMARK_ORDER = (
    "previous_day_high", "previous_day_low", "asia_high", "asia_low",
    "london_high_so_far", "london_low_so_far", "us_high_so_far", "us_low_so_far",
)


def active_session_at(at: datetime) -> str:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("at must be timezone-aware")
    local_at = at.astimezone(_server_timezone())
    hour = local_at.time()
    if time(ASIA_RANGE_START_HOUR) <= hour < time(ASIA_RANGE_END_HOUR):
        return "asia"
    if _LONDON_START <= hour < _LONDON_END:
        return "london"
    if _US_START <= hour < _US_END:
        return "us"
    return "transition"


def _closed_before_signal(bars: Sequence[MarketBar], signal_at: datetime) -> list[MarketBar]:
    return [
        bar for bar in bars
        if bar.timestamp + timedelta(minutes=5) <= signal_at
    ]


def _levels(bars: Sequence[MarketBar]) -> tuple[float | None, float | None]:
    if not bars:
        return None, None
    return max(bar.high for bar in bars), min(bar.low for bar in bars)


def build_session_landmark_context(
    bars_m5: Sequence[MarketBar],
    signal_at: datetime,
    signal_price: float,
    side: Side | None,
    *,
    atr_m5: float | None = None,
    atr_m15: float | None = None,
) -> SessionLandmarkContext:
    if signal_at.tzinfo is None or signal_at.utcoffset() is None:
        raise ValueError("signal_at must be timezone-aware")
    local_at = signal_at.astimezone(_server_timezone())
    closed = _closed_before_signal(bars_m5, signal_at)
    local_bars = [(bar, bar.timestamp.astimezone(_server_timezone())) for bar in closed]

    previous_day = local_at.date() - timedelta(days=1)
    previous_day_bars = [bar for bar, local in local_bars if local.date() == previous_day]
    pdh, pdl = _levels(previous_day_bars)
    def window(start: time, end: time) -> list[MarketBar]:
        return [
            bar for bar, local in local_bars
            if local.date() == local_at.date() and start <= local.time() < end
        ]

    asia = window(time(ASIA_RANGE_START_HOUR), time(ASIA_RANGE_END_HOUR))
    london = window(_LONDON_START, _LONDON_END)
    us = window(_US_START, _US_END)
    ah, al = _levels(asia)
    lh, ll = _levels(london)
    uh, ul = _levels(us)

    active = active_session_at(signal_at)
    active_bars = {"asia": asia, "london": london, "us": us}.get(active, [])
    active_high, active_low = _levels(active_bars)
    active_range = (
        active_high - active_low
        if active_high is not None and active_low is not None
        else None
    )
    active_position = None
    active_location = None
    if active_low is not None and active_high is not None and active_range and active_range > 0:
        if signal_price < active_low:
            active_position = 0.0
            active_location = SessionLandmarkLocation.BELOW_RANGE
        elif signal_price > active_high:
            active_position = 1.0
            active_location = SessionLandmarkLocation.ABOVE_RANGE
        else:
            active_position = (signal_price - active_low) / active_range
            active_location = SessionLandmarkLocation.INSIDE_RANGE
    landmarks = {
        name: value for name, value in zip(
            _LANDMARK_ORDER, (pdh, pdl, ah, al, lh, ll, uh, ul), strict=True
        ) if value is not None
    }
    nearest_name, nearest_price = (
        min(landmarks.items(), key=lambda item: (abs(item[1] - signal_price), _LANDMARK_ORDER.index(item[0])))
        if landmarks else (None, None)
    )
    distance = abs(nearest_price - signal_price) if nearest_price is not None else None
    return SessionLandmarkContext(
        at=signal_at,
        active_session=active,
        previous_day_high=pdh,
        previous_day_low=pdl,
        asia_high=ah,
        asia_low=al,
        london_high_so_far=lh,
        london_low_so_far=ll,
        us_high_so_far=uh,
        us_low_so_far=ul,
        nearest_landmark_type=nearest_name,
        nearest_landmark_price=nearest_price,
        nearest_landmark_distance=distance,
        nearest_landmark_distance_atr_m5=(distance / atr_m5 if distance is not None and atr_m5 and atr_m5 > 0 else None),
        nearest_landmark_distance_atr_m15=(distance / atr_m15 if distance is not None and atr_m15 and atr_m15 > 0 else None),
        side_aligned_distance_to_nearest_landmark=(
            (nearest_price - signal_price) if side == Side.BUY and nearest_price is not None
            else (signal_price - nearest_price) if side == Side.SELL and nearest_price is not None else None
        ),
        active_session_high=active_high,
        active_session_low=active_low,
        active_session_range=active_range,
        active_session_range_atr_m5=(active_range / atr_m5 if active_range is not None and atr_m5 and atr_m5 > 0 else None),
        active_session_position=active_position,
        active_session_location=active_location,
    )
