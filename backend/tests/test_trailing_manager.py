from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trailing_manager import TrailingManagerConfig
from app.services.trailing_manager import (
    propose_trailing_adjustment,
    replay_trailing_trade,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 23, 10, 0, tzinfo=TZ)


def bar(index: int, *, open_: float, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        symbol="BTCUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def trade(side: Side = Side.BUY) -> ShadowPaperTrade:
    if side == Side.BUY:
        entry, stop, target = 100.0, 98.0, 102.0
    else:
        entry, stop, target = 100.0, 102.0, 98.0
    return ShadowPaperTrade(
        trade_id="t1",
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=side,
        signal_at=START,
        entry_bar_at=START,
        opened_at=START,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        spread_at_entry=0.0,
        lots=0.01,
        risk_eur=2.0,
        risk_distance=2.0,
        target_r=1.0,
        max_holding_bars=6,
    )


def test_buy_trailing_tightens_stop_and_extends_target_only_after_protection() -> None:
    t = trade()
    bars = [
        bar(0, open_=100.0, high=100.7, low=99.9, close=100.5),
        bar(1, open_=100.5, high=101.5, low=100.3, close=101.3),
        bar(2, open_=101.3, high=101.9, low=101.1, close=101.8),
    ]

    adjustment = propose_trailing_adjustment(
        trade=t,
        closed_bars=bars,
        current_stop=t.stop_price,
        current_target=t.target_price,
        config=TrailingManagerConfig(enable_target_extension=True),
    )

    assert adjustment is not None
    assert adjustment.stop_after >= t.stop_price
    assert adjustment.stop_after >= t.entry_price
    assert adjustment.target_after == 103.0
    assert "break_even_locked" in adjustment.reason
    assert "target_extended_on_protected_momentum" in adjustment.reason


def test_sell_trailing_never_widens_initial_stop() -> None:
    t = trade(Side.SELL)
    bars = [
        bar(0, open_=100.0, high=100.1, low=99.3, close=99.5),
        bar(1, open_=99.5, high=99.7, low=98.7, close=98.9),
        bar(2, open_=98.9, high=99.0, low=98.1, close=98.2),
    ]

    adjustment = propose_trailing_adjustment(
        trade=t,
        closed_bars=bars,
        current_stop=t.stop_price,
        current_target=t.target_price,
        config=TrailingManagerConfig(enable_target_extension=True),
    )

    assert adjustment is not None
    assert adjustment.stop_after <= t.stop_price
    assert adjustment.stop_after <= t.entry_price
    assert adjustment.target_after == 97.0


def test_replay_uses_adjustments_only_after_closed_bars() -> None:
    t = trade()
    bars = [
        bar(0, open_=100.0, high=100.7, low=99.9, close=100.5),
        bar(1, open_=100.5, high=101.5, low=100.3, close=101.3),
        bar(2, open_=101.3, high=101.9, low=101.1, close=101.8),
        bar(3, open_=101.8, high=103.2, low=101.6, close=103.0),
    ]

    result = replay_trailing_trade(
        t,
        bars,
        config=TrailingManagerConfig(enable_target_extension=True),
    )

    assert result.result_r == 1.5
    assert result.exit_reason == "extended_target"
    assert result.maximum_added_risk_r == 0
    assert result.adjustments
    assert result.adjustments[0].at <= bars[2].timestamp


def test_stop_only_mode_keeps_original_target() -> None:
    t = trade()
    bars = [
        bar(0, open_=100.0, high=100.7, low=99.9, close=100.5),
        bar(1, open_=100.5, high=101.5, low=100.3, close=101.3),
        bar(2, open_=101.3, high=101.9, low=101.1, close=101.8),
    ]

    adjustment = propose_trailing_adjustment(
        trade=t,
        closed_bars=bars,
        current_stop=t.stop_price,
        current_target=t.target_price,
        config=TrailingManagerConfig(
            enable_stop_trailing=True,
            enable_target_extension=False,
        ),
    )

    assert adjustment is not None
    assert adjustment.stop_after >= t.entry_price
    assert adjustment.target_after == t.target_price


def test_disabled_manager_preserves_static_target_exit() -> None:
    t = trade()
    bars = [
        bar(0, open_=100.0, high=100.7, low=99.9, close=100.5),
        bar(1, open_=100.5, high=102.2, low=100.3, close=102.0),
    ]

    result = replay_trailing_trade(
        t,
        bars,
        config=TrailingManagerConfig(
            enable_stop_trailing=False,
            enable_target_extension=False,
        ),
    )

    assert result.result_r == t.target_r
    assert result.exit_reason == "target"
    assert result.final_stop == t.stop_price
    assert result.final_target == t.target_price
    assert result.adjustments == []


def test_target_only_mode_extends_target_without_moving_stop() -> None:
    t = trade()
    bars = [
        bar(0, open_=100.0, high=100.8, low=99.9, close=100.6),
        bar(1, open_=100.6, high=101.4, low=100.5, close=101.2),
        bar(2, open_=101.2, high=101.8, low=101.1, close=101.6),
    ]

    adjustment = propose_trailing_adjustment(
        trade=t,
        closed_bars=bars,
        current_stop=t.stop_price,
        current_target=t.target_price,
        config=TrailingManagerConfig(
            enable_stop_trailing=False,
            enable_target_extension=True,
            target_extension_requires_protected_stop=False,
        ),
    )

    assert adjustment is not None
    assert adjustment.stop_after == t.stop_price
    assert adjustment.target_after == 103.0
