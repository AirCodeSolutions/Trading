from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.precursor_forward_research import (
    _independent_outcomes,
    _resolve_symbol_outcomes,
    _summary,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 24, 6, 0, tzinfo=TZ)


def bar(index: int, *, close: float, high: float, low: float) -> MarketBar:
    return MarketBar(
        symbol="EURUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * index),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def precursor(
    index: int,
    *,
    side: Side,
    pattern: OpportunityCausalPattern = OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
) -> CausalPrecursorObservation:
    latest = START + timedelta(minutes=5 * index)
    return CausalPrecursorObservation(
        symbol="EURUSD",
        first_seen_at=latest + timedelta(minutes=5),
        latest_closed_m5_at=latest,
        pattern=pattern,
        side=side,
        context=OpportunityCausalContext(pattern=pattern, side=side),
    )


def test_resolve_forward_outcome_orients_buy_and_requires_complete_horizon() -> None:
    bars = [
        bar(i, close=100 + i * 0.1, high=100.2 + i * 0.1, low=99.8 + i * 0.1)
        for i in range(20)
    ]
    rows = [
        precursor(3, side=Side.BUY),
        precursor(16, side=Side.BUY),
    ]

    outcomes, pending = _resolve_symbol_outcomes(
        rows,
        bars,
        horizon_bars=4,
    )

    assert len(outcomes) == 1
    assert pending == 1
    result = outcomes[0]
    assert result.favorable_mfe_atr > 0
    assert result.adverse_mae_atr >= 0
    assert result.signed_close_return_atr > 0
    assert result.close_aligned is True


def test_resolve_forward_outcome_orients_sell() -> None:
    bars = [
        bar(i, close=100 - i * 0.1, high=100.2 - i * 0.1, low=99.8 - i * 0.1)
        for i in range(20)
    ]

    outcomes, pending = _resolve_symbol_outcomes(
        [precursor(3, side=Side.SELL)],
        bars,
        horizon_bars=4,
    )

    assert pending == 0
    assert len(outcomes) == 1
    result = outcomes[0]
    assert result.signed_close_return_atr > 0
    assert result.close_aligned is True


def test_independent_outcomes_exclude_overlapping_precursors_same_symbol() -> None:
    bars = [
        bar(i, close=100 + i * 0.1, high=100.2 + i * 0.1, low=99.8 + i * 0.1)
        for i in range(32)
    ]
    resolved, _ = _resolve_symbol_outcomes(
        [
            precursor(3, side=Side.BUY),
            precursor(5, side=Side.BUY),
            precursor(16, side=Side.BUY),
        ],
        bars,
        horizon_bars=12,
    )

    selected = _independent_outcomes(resolved, horizon_bars=12)

    assert len(resolved) == 3
    assert len(selected) == 2
    assert selected[0].first_seen_at == precursor(3, side=Side.BUY).first_seen_at
    assert selected[1].first_seen_at == precursor(16, side=Side.BUY).first_seen_at


def test_summary_uses_independent_rows_only() -> None:
    bars = [
        bar(i, close=100 + i * 0.1, high=100.2 + i * 0.1, low=99.8 + i * 0.1)
        for i in range(32)
    ]
    raw, _ = _resolve_symbol_outcomes(
        [
            precursor(3, side=Side.BUY),
            precursor(5, side=Side.BUY),
            precursor(16, side=Side.BUY),
        ],
        bars,
        horizon_bars=12,
    )
    independent = _independent_outcomes(raw, horizon_bars=12)

    summary = _summary(
        label="all",
        raw=raw,
        independent=independent,
    )

    assert summary.raw_resolved == 3
    assert summary.independent_resolved == 2
    assert summary.close_alignment_rate == 1.0
    assert summary.favorable_dominance_rate == 1.0
