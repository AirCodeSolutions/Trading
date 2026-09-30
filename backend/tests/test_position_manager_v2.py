from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.position_manager import PositionManagerV2Action, PositionManagerV2State
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.services.position_manager_v2 import replay_position_manager_v2

START = datetime(2026, 9, 30, 10, tzinfo=ZoneInfo("Europe/Athens"))


def trade(side=Side.BUY, *, target=103.0, max_bars=6):
    target_price = target if side is Side.BUY else 100 - (target - 100)
    target_r = abs(target_price - 100) / 2
    return ShadowPaperTrade(
        trade_id="T1", symbol="XAUUSD", mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        side=side, signal_at=START, entry_bar_at=START, opened_at=START,
        entry_price=100, stop_price=98 if side is Side.BUY else 102,
        target_price=target_price, spread_at_entry=0.1,
        lots=1, risk_eur=100, risk_distance=2, target_r=target_r,
        max_holding_bars=max_bars,
    )


def bar(index, *, close, high=None, low=None):
    at = START + timedelta(minutes=index * 5)
    return MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=at, open=100, high=high or max(100, close), low=low or min(100, close), close=close)


def test_no_follow_through_is_causal_and_descriptive():
    snapshot, comparison = replay_position_manager_v2(trade(), [bar(0, close=99.9), bar(1, close=99.8), bar(2, close=99.7)])
    assert snapshot is not None
    assert snapshot.state is PositionManagerV2State.NO_FOLLOW_THROUGH
    assert snapshot.proposed_action is PositionManagerV2Action.EXIT_NO_FOLLOW_THROUGH
    assert comparison.no_follow_through_used


def test_protect_and_trailing_never_widen_buy_stop():
    snapshot, comparison = replay_position_manager_v2(trade(target=110), [bar(0, close=101), bar(1, close=101.8), bar(2, close=102.0), bar(3, close=102.2)])
    assert snapshot is not None
    assert snapshot.current_stop >= snapshot.initial_stop
    assert comparison.v2_result_r is not None


def test_sell_stop_never_moves_up_and_same_bar_stop_is_priority():
    snapshot, _ = replay_position_manager_v2(trade(Side.SELL, target=97), [bar(0, close=99, high=102.2, low=97)])
    assert snapshot is not None
    assert snapshot.current_stop <= snapshot.initial_stop


def test_v2_uses_same_trade_population_as_baseline():
    _, comparison = replay_position_manager_v2(trade(target=103), [bar(0, close=100), bar(1, close=103, high=103)])
    assert comparison.trade_id == "T1"
    assert comparison.baseline_result_r == 1.5
    assert comparison.v2_result_r is not None
    assert comparison.pending is False


def test_incomplete_horizon_is_pending_and_never_safety_timeout():
    snapshot, comparison = replay_position_manager_v2(
        trade(target=110, max_bars=18),
        [bar(0, close=100.2), bar(1, close=100.3)],
    )
    assert snapshot is not None
    assert snapshot.state is not PositionManagerV2State.SAFETY_TIMEOUT
    assert snapshot.proposed_exit_price is None
    assert snapshot.proposed_exit_r is None
    assert snapshot.bars_held == 2
    assert comparison.pending is True
    assert comparison.v2_result_r is None


def test_partial_entry_bar_is_ignored_and_first_full_bar_is_used():
    opened = START + timedelta(minutes=1)
    opened_trade = trade(target=103).model_copy(update={"opened_at": opened})
    partial = MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=START, open=100, high=110, low=90, close=100)
    first_full = bar(1, close=100.5, high=100.8, low=99.9)
    snapshot, comparison = replay_position_manager_v2(opened_trade, [partial, first_full])
    assert snapshot is not None
    assert snapshot.bars_held == 1
    assert comparison.pending is True
    assert snapshot.state is not PositionManagerV2State.CLOSED_STOP
    assert snapshot.state is not PositionManagerV2State.CLOSED_TARGET


def test_timeout_occurs_only_at_exact_horizon():
    snapshot, comparison = replay_position_manager_v2(
        trade(target=110, max_bars=3),
        [bar(0, close=100.2), bar(1, close=100.3), bar(2, close=100.4)],
    )
    assert snapshot is not None
    assert snapshot.state is PositionManagerV2State.SAFETY_TIMEOUT
    assert comparison.pending is False
    assert comparison.v2_exit_reason == "safety_timeout"
    assert comparison.bars_held_v2 == 3


def test_mfe_and_mae_use_extremes_for_buy():
    snapshot, _ = replay_position_manager_v2(
        trade(target=110, max_bars=1),
        [bar(0, close=100.5, high=104, low=99)],
    )
    assert snapshot is not None
    assert snapshot.mfe_r == 2.0
    assert snapshot.mae_r == 0.5


def test_mfe_and_mae_use_sell_ask_adjusted_extremes():
    snapshot, _ = replay_position_manager_v2(
        trade(Side.SELL, target=110, max_bars=1),
        [bar(0, close=99.5, high=101, low=95)],
    )
    assert snapshot is not None
    assert snapshot.mfe_r == pytest.approx(2.45)
    assert snapshot.mae_r == pytest.approx(0.55)
