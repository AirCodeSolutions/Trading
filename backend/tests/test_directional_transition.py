from datetime import UTC, datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side
from app.services.opportunity_strategies import _directional_transition_candidate
from app.services.shadow_scanner import _directional_transition_signal

START = datetime(2026, 1, 1, tzinfo=UTC)


def bars() -> list[MarketBar]:
    return [
        MarketBar(
            symbol="TEST",
            timeframe=Timeframe.M5,
            timestamp=START + timedelta(minutes=5 * index),
            open=100.0 + index * 0.01,
            high=100.2 + index * 0.01,
            low=99.8 + index * 0.01,
            close=100.1 + index * 0.01,
            volume=100,
        )
        for index in range(40)
    ]


def regime(direction: int, state: MarketRegime) -> RegimeSnapshot:
    return RegimeSnapshot(
        symbol="TEST",
        at=START,
        regime=state,
        direction=direction,
        confidence=0.8,
        atr=1.5,
        atr_ratio=1.1,
        efficiency=0.7,
        shock_ratio=1.0,
        reason="test",
    )


def test_directional_transition_candidate_enters_next_m5_bar() -> None:
    series = bars()
    candidate = _directional_transition_candidate(
        series,
        30,
        regime(1, MarketRegime.DIRECTIONAL),
    )

    assert candidate is not None
    assert candidate.side == Side.BUY
    assert candidate.signal_index == 30
    assert candidate.entry_index == 31
    assert candidate.entry_at == series[31].timestamp
    assert candidate.structural_stop == series[31].open - 1.2
    assert candidate.target_r == 1.8
    assert candidate.max_holding_bars == 18


def test_shadow_transition_requires_exact_new_m15_close() -> None:
    series = bars()
    current = regime(1, MarketRegime.DIRECTIONAL)
    previous = regime(0, MarketRegime.BALANCED)

    missing = _directional_transition_signal(
        series,
        current,
        previous,
        False,
    )
    signal = _directional_transition_signal(
        series,
        current,
        previous,
        True,
    )

    assert missing is None
    assert signal is not None
    assert signal[0] == Side.BUY
    assert signal[2] == 1.8
    assert signal[3] == 18


def test_shadow_transition_does_not_repeat_persistent_direction() -> None:
    series = bars()
    current = regime(-1, MarketRegime.DIRECTIONAL)
    previous = regime(-1, MarketRegime.DIRECTIONAL)

    signal = _directional_transition_signal(
        series,
        current,
        previous,
        True,
    )

    assert signal is None
