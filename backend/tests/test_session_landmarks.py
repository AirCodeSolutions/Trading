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


def test_missing_history_returns_none_without_zeroes() -> None:
    signal = datetime(2026, 9, 28, 1, 0, tzinfo=TZ)
    context = build_session_landmark_context([], signal, 10, Side.BUY)
    assert context.previous_day_high is None
    assert context.nearest_landmark_price is None
    assert context.active_session_range_position is None if hasattr(context, "active_session_range_position") else context.active_session_position is None
