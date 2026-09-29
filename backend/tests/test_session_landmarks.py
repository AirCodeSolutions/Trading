from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.services.session_landmarks import build_session_landmark_context

TZ = ZoneInfo("Europe/Athens")


def bar(at: datetime, high: float, low: float) -> MarketBar:
    return MarketBar(symbol="EURUSD", timeframe=Timeframe.M5, timestamp=at, open=low, high=high, low=low, close=high, volume=1)


def test_previous_day_and_session_levels_exclude_future_bars() -> None:
    signal = datetime(2026, 9, 28, 10, 0, tzinfo=TZ)
    bars = [
        bar(datetime(2026, 9, 27, 12, 0, tzinfo=TZ), 10, 5),
        bar(datetime(2026, 9, 28, 2, 0, tzinfo=TZ), 8, 6),
        bar(datetime(2026, 9, 28, 9, 55, tzinfo=TZ), 20, 1),  # partial at signal, excluded
        bar(datetime(2026, 9, 28, 10, 0, tzinfo=TZ), 30, 0.5),  # future, excluded
    ]
    context = build_session_landmark_context(bars, signal, 7, Side.BUY, atr_m5=2, atr_m15=4)
    assert context.previous_day_high == 10
    assert context.asia_high == 20
    assert context.asia_low == 1
    assert context.london_high_so_far is None
    assert context.nearest_landmark_distance_atr_m5 == 1.0


def test_london_so_far_and_zero_range_are_causal() -> None:
    signal = datetime(2026, 9, 28, 11, 0, tzinfo=TZ)
    bars = [
        bar(datetime(2026, 9, 28, 10, 0, tzinfo=TZ), 12, 10),
        bar(datetime(2026, 9, 28, 10, 55, tzinfo=TZ), 15, 9),
        bar(datetime(2026, 9, 28, 11, 0, tzinfo=TZ), 99, 1),
    ]
    context = build_session_landmark_context(bars, signal, 12, Side.SELL)
    assert context.london_high_so_far == 15
    assert context.london_low_so_far == 9
    assert context.active_session == "london"
    assert context.active_session_position == 0.5


def test_session_position_preserves_range_location_at_boundaries_and_breakouts() -> None:
    signal = datetime(2026, 9, 28, 11, 0, tzinfo=TZ)
    bars = [bar(datetime(2026, 9, 28, 10, 0, tzinfo=TZ), 20, 10)]

    inside = build_session_landmark_context(bars, signal, 15, Side.BUY)
    above = build_session_landmark_context(bars, signal, 21, Side.BUY)
    below = build_session_landmark_context(bars, signal, 9, Side.BUY)
    at_high = build_session_landmark_context(bars, signal, 20, Side.BUY)
    at_low = build_session_landmark_context(bars, signal, 10, Side.BUY)

    assert inside.active_session_position == 0.5
    assert inside.active_session_location == "INSIDE_RANGE"
    assert above.active_session_position == 1.0
    assert above.active_session_location == "ABOVE_RANGE"
    assert below.active_session_position == 0.0
    assert below.active_session_location == "BELOW_RANGE"
    assert at_high.active_session_position == 1.0
    assert at_high.active_session_location == "INSIDE_RANGE"
    assert at_low.active_session_position == 0.0
    assert at_low.active_session_location == "INSIDE_RANGE"


def test_zero_range_has_no_session_position_or_location() -> None:
    signal = datetime(2026, 9, 28, 11, 0, tzinfo=TZ)
    bars = [bar(datetime(2026, 9, 28, 10, 0, tzinfo=TZ), 10, 10)]
    context = build_session_landmark_context(bars, signal, 10, Side.BUY)

    assert context.active_session_position is None
    assert context.active_session_location is None


def test_missing_history_returns_none_without_zeroes() -> None:
    signal = datetime(2026, 9, 28, 1, 0, tzinfo=TZ)
    context = build_session_landmark_context([], signal, 10, Side.BUY)
    assert context.previous_day_high is None
    assert context.nearest_landmark_price is None
    assert context.active_session_range_position is None if hasattr(context, "active_session_range_position") else context.active_session_position is None
