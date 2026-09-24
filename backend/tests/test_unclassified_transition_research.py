from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.unclassified_transition_research import (
    first_directional_transition,
    summarize_waiting_rows,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 6, 1, tzinfo=TZ)


def _bars(count: int = 12) -> list[MarketBar]:
    return [
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=START + timedelta(minutes=5 * index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=100,
        )
        for index in range(count)
    ]


def test_first_directional_transition_ignores_nondirectional_states(
    monkeypatch,
) -> None:
    contexts = {
        5: OpportunityCausalContext(
            pattern=OpportunityCausalPattern.COMPRESSION_STATE,
        ),
        6: OpportunityCausalContext(
            pattern=OpportunityCausalPattern.STRUCTURAL_EXTREME,
        ),
        7: OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.SELL,
        ),
    }

    monkeypatch.setattr(
        "app.services.unclassified_transition_research._classify_causal_context",
        lambda **kwargs: contexts.get(
            kwargs["index"],
            OpportunityCausalContext(),
        ),
    )

    result = first_directional_transition(
        _bars(),
        [2.0] * 12,
        4,
        episode_side=Side.SELL,
        max_wait_bars=3,
    )

    assert result is not None
    index, context = result
    assert index == 7
    assert context.pattern == OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT
    assert context.side == Side.SELL


def test_first_directional_transition_validates_wait_window() -> None:
    with pytest.raises(ValueError, match="max_wait_bars"):
        first_directional_transition(
            _bars(),
            [2.0] * 12,
            4,
            episode_side=Side.BUY,
            max_wait_bars=0,
        )


def test_waiting_summary_separates_direction_from_trade_economics() -> None:
    rows = [
        {
            "transition_pattern": "directional_displacement",
            "aligned": True,
            "bars_waited": 1,
            "move_consumed_atr": 0.5,
            "result_r": 1.0,
        },
        {
            "transition_pattern": "compression_breakout",
            "aligned": True,
            "bars_waited": 2,
            "move_consumed_atr": 0.8,
            "result_r": -1.0,
        },
        {
            "transition_pattern": "auction_failure_reclaim",
            "aligned": False,
            "bars_waited": 3,
            "move_consumed_atr": 0.6,
            "result_r": -0.5,
        },
        {
            "transition_pattern": None,
            "aligned": False,
            "bars_waited": 0,
            "move_consumed_atr": 0.0,
            "result_r": None,
        },
    ]

    summary = summarize_waiting_rows(rows)

    assert summary["episodes"] == 4
    assert summary["transitions"] == 3
    assert summary["transition_coverage"] == pytest.approx(0.75)
    assert summary["alignment_rate"] == pytest.approx(2 / 3)
    assert summary["average_wait_bars"] == pytest.approx(2.0)
    assert summary["average_move_consumed_atr"] == pytest.approx(1.9 / 3)
    assert summary["executed"] == 3
    assert summary["expectancy_r"] == pytest.approx(-1 / 6)
    assert summary["total_r"] == pytest.approx(-0.5)
    assert summary["profit_factor"] == pytest.approx(2 / 3)
    assert summary["max_drawdown_r"] == pytest.approx(1.5)
