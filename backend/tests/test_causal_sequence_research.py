from datetime import UTC, datetime, timedelta

from app.domain.causal_economic_matrix import DirectionalConsistency
from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.causal_economic_matrix import _directional_consistency
from app.services.causal_sequence_research import (
    _first_touch_directional_success,
    _sequence_direction,
)


def context(pattern: OpportunityCausalPattern, side: Side | None) -> OpportunityCausalContext:
    return OpportunityCausalContext(pattern=pattern, side=side)


def test_sequence_direction_uses_most_recent_directional_context() -> None:
    contexts = [
        context(OpportunityCausalPattern.COMPRESSION_STATE, None),
        context(OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT, Side.BUY),
        context(OpportunityCausalPattern.STRUCTURAL_EXTREME, None),
    ]

    assert _sequence_direction(contexts) == Side.BUY


def test_sequence_direction_is_none_when_all_contexts_are_neutral() -> None:
    contexts = [
        context(OpportunityCausalPattern.UNCLASSIFIED, None),
        context(OpportunityCausalPattern.COMPRESSION_STATE, None),
        context(OpportunityCausalPattern.STRUCTURAL_EXTREME, None),
    ]

    assert _sequence_direction(contexts) is None


def test_sequence_consistency_reuses_deterministic_split_rule() -> None:
    assert (
        _directional_consistency(0.61, 0.57, 0.55)
        == DirectionalConsistency.ALIGNED_STABLE
    )
    assert (
        _directional_consistency(0.39, 0.42, 0.45)
        == DirectionalConsistency.OPPOSED_STABLE
    )
    assert (
        _directional_consistency(0.61, 0.42, 0.55)
        == DirectionalConsistency.MIXED
    )


def market_bar(index: int, *, high: float, low: float, close: float = 100.0) -> MarketBar:
    return MarketBar(
        symbol="TEST",
        timeframe=Timeframe.M5,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index),
        open=100.0,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def test_first_touch_directional_success_target_before_stop() -> None:
    bars = [
        market_bar(0, high=100.1, low=99.9),
        market_bar(1, high=101.6, low=99.8),
        market_bar(2, high=100.2, low=98.0),
    ]

    assert _first_touch_directional_success(
        bars=bars,
        index=0,
        atr_value=1.0,
        side=Side.BUY,
        threshold_atr=1.5,
        horizon_bars=2,
    ) is True


def test_first_touch_directional_success_stop_before_target() -> None:
    bars = [
        market_bar(0, high=100.1, low=99.9),
        market_bar(1, high=100.2, low=98.4),
        market_bar(2, high=102.0, low=99.9),
    ]

    assert _first_touch_directional_success(
        bars=bars,
        index=0,
        atr_value=1.0,
        side=Side.BUY,
        threshold_atr=1.5,
        horizon_bars=2,
    ) is False


def test_first_touch_directional_success_excludes_ambiguous_bar() -> None:
    bars = [
        market_bar(0, high=100.1, low=99.9),
        market_bar(1, high=101.6, low=98.4),
    ]

    assert _first_touch_directional_success(
        bars=bars,
        index=0,
        atr_value=1.0,
        side=Side.BUY,
        threshold_atr=1.5,
        horizon_bars=1,
    ) is None
