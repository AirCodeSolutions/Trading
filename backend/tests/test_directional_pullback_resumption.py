from datetime import UTC, datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side
from app.services.opportunity_strategies import (
    _directional_pullback_resumption_candidate,
)
from app.services.shadow_scanner import _directional_pullback_resumption_signal

START = datetime(2026, 1, 1, tzinfo=UTC)


def bar(
    index: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        symbol="GBPUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def bullish_setup() -> list[MarketBar]:
    return [
        bar(0, open_=100.0, high=100.3, low=99.9, close=100.1),
        bar(1, open_=100.1, high=100.4, low=100.0, close=100.2),
        bar(2, open_=100.5, high=100.6, low=99.8, close=100.2),
        bar(3, open_=100.3, high=100.4, low=99.9, close=100.1),
        bar(4, open_=100.15, high=100.7, low=100.0, close=100.5),
        bar(5, open_=100.55, high=100.8, low=100.4, close=100.7),
    ]


def regime(direction: int = 1) -> RegimeSnapshot:
    return RegimeSnapshot(
        symbol="GBPUSD",
        at=START,
        regime=MarketRegime.DIRECTIONAL,
        direction=direction,
        confidence=0.8,
        atr=1.5,
        atr_ratio=1.1,
        efficiency=0.7,
        shock_ratio=1.0,
        reason="test",
    )


def test_candidate_waits_for_two_bar_pullback_then_enters_next_m5() -> None:
    bars = bullish_setup()
    atr = [1.0] * len(bars)

    candidate = _directional_pullback_resumption_candidate(
        bars,
        atr,
        4,
        regime(),
    )

    assert candidate is not None
    assert candidate.side == Side.BUY
    assert candidate.signal_index == 4
    assert candidate.entry_index == 5
    assert candidate.entry_at == bars[5].timestamp
    assert candidate.structural_stop == 99.7
    assert candidate.target_r == 2.0
    assert candidate.max_holding_bars == 12


def test_runtime_signal_matches_historical_pullback_geometry() -> None:
    bars = bullish_setup()
    atr = [1.0] * len(bars)

    candidate = _directional_pullback_resumption_candidate(
        bars,
        atr,
        4,
        regime(),
    )
    signal = _directional_pullback_resumption_signal(
        bars[:5],
        atr[:5],
        regime(),
    )

    assert candidate is not None
    assert signal is not None
    assert signal[0] == candidate.side
    assert signal[1] == candidate.structural_stop
    assert signal[2] == candidate.target_r
    assert signal[3] == candidate.max_holding_bars


def test_pullback_requires_two_counter_directional_m5_bars() -> None:
    bars = bullish_setup()
    bars[2] = bar(
        2,
        open_=100.2,
        high=100.6,
        low=99.8,
        close=100.5,
    )

    signal = _directional_pullback_resumption_signal(
        bars[:5],
        [1.0] * 5,
        regime(),
    )

    assert signal is None
