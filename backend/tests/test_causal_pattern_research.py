from datetime import datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.causal_pattern_research import (
    _historical_causal_episodes,
    _split_summary,
)
from app.services.trading_intelligence import _atr_series

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 6, 1, 0, 0, tzinfo=TZ)


def make_bar(index: int, close: float) -> MarketBar:
    at = START + timedelta(minutes=5 * index)
    return MarketBar(
        symbol="BTCUSD",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=close - 0.5,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
    )


def test_split_summary_counts_alignment() -> None:
    rows = [
        {
            "move_atr": 2.0,
            "context": OpportunityCausalContext(
                pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
                side=Side.BUY,
                aligned_with_move=True,
            ),
        },
        {
            "move_atr": 3.0,
            "context": OpportunityCausalContext(
                pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
                side=Side.BUY,
                aligned_with_move=False,
            ),
        },
        {
            "move_atr": 4.0,
            "context": OpportunityCausalContext(
                pattern=OpportunityCausalPattern.COMPRESSION_STATE,
                side=None,
                aligned_with_move=None,
            ),
        },
    ]

    summary = _split_summary(rows)

    assert summary.episodes == 3
    assert summary.directional_episodes == 2
    assert summary.aligned == 1
    assert summary.opposed == 1
    assert summary.no_direction == 1
    assert summary.alignment_rate == 0.5
    assert summary.average_move_atr == 3.0


def test_historical_causal_episodes_are_deduplicated_by_horizon() -> None:
    bars = []
    for index in range(120):
        close = 100.0 + index * 0.4
        bars.append(make_bar(index, close))
    atr = _atr_series(bars)

    rows = _historical_causal_episodes(
        bars=bars,
        atr=atr,
        move_threshold_atr=1.5,
        horizon_bars=12,
    )

    assert rows
    for left, right in pairwise(rows):
        assert right["birth_at"] - left["birth_at"] >= timedelta(minutes=60)
    assert all(row["episode_side"] == Side.BUY for row in rows)
    assert all(
        isinstance(row["context"], OpportunityCausalContext)
        for row in rows
    )
