from datetime import UTC, datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side
from app.services.shadow_scanner import _post_shock_research_context


def m15_bars() -> list[MarketBar]:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    bars: list[MarketBar] = []
    price = 100.0
    for index in range(60):
        bars.append(
            MarketBar(
                symbol="XAUUSD",
                timeframe=Timeframe.M15,
                timestamp=start + timedelta(minutes=15 * index),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price + 0.2,
            )
        )
        price += 0.2
    bars[-1] = bars[-1].model_copy(
        update={"open": bars[-2].close, "high": bars[-2].close + 10, "low": bars[-2].close - 1, "close": bars[-2].close + 9}
    )
    return bars


def regime() -> RegimeSnapshot:
    return RegimeSnapshot(
        symbol="XAUUSD",
        at=datetime(2026, 9, 1, 14, 45, tzinfo=UTC),
        regime=MarketRegime.POST_SHOCK,
        direction=1,
        confidence=1,
        atr=2,
        atr_ratio=2,
        efficiency=1,
        shock_ratio=5,
        reason="test",
    )


def m5_bars(start: datetime, closes: list[float]) -> list[MarketBar]:
    return [
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=start + timedelta(minutes=5 * index),
            open=close - 0.5,
            high=close + 1,
            low=close - 1,
            close=close,
        )
        for index, close in enumerate(closes)
    ]


def test_latency_zero_still_measures_closed_shock_path() -> None:
    m15 = m15_bars()
    shock_at = m15[-1].timestamp
    m5 = m5_bars(shock_at, [108, 109, 110])

    context = _post_shock_research_context(m5, m15, 59, regime(), Side.BUY, 110)

    assert context is not None
    assert context.post_shock_latency_minutes == 0
    assert context.post_shock_elapsed_complete_m5_bars == 3
    assert context.pre_signal_consumed_move is not None
    assert context.pre_signal_mfe is not None


def test_latency_ten_minutes_includes_two_additional_m5_bars() -> None:
    m15 = m15_bars()
    shock_at = m15[-1].timestamp
    m5 = m5_bars(shock_at, [108, 109, 110, 111, 112])

    context = _post_shock_research_context(m5, m15, 59, regime(), Side.BUY, 112)

    assert context is not None
    assert context.post_shock_latency_minutes == 10
    assert context.post_shock_elapsed_complete_m5_bars == 5


def test_future_m5_is_excluded_and_sell_is_symmetric() -> None:
    m15 = m15_bars()
    shock_at = m15[-1].timestamp
    m5 = m5_bars(shock_at, [98, 97, 96, 10])
    m5 = [bar for bar in m5 if bar.timestamp <= shock_at + timedelta(minutes=10)]

    context = _post_shock_research_context(m5, m15, 59, regime().model_copy(update={"direction": -1}), Side.SELL, 96)

    assert context is not None
    assert context.post_shock_elapsed_complete_m5_bars == 3
    assert context.pre_signal_consumed_move is not None
    assert context.pre_signal_mfe is not None
    assert context.pre_signal_mae is not None
