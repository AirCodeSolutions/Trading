from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.opportunity import OpportunityMechanism
from app.domain.session_landmark import SessionLandmarkContext
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.services.authority_recovery_clear_path import (
    HYPOTHESIS_ID,
    MIN_SELECTED_OBSERVATIONS,
    clear_path_to_existing_target,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 10, 1, 17, 30, tzinfo=TZ)


def trade(side: Side, *, target: float, context: SessionLandmarkContext) -> ShadowPaperTrade:
    signal = NOW - timedelta(hours=1)
    return ShadowPaperTrade(
        trade_id="probe", symbol="XAUUSD", mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        side=side, signal_at=signal, entry_bar_at=signal, opened_at=signal,
        entry_price=100.0, stop_price=99.0 if side is Side.BUY else 101.0,
        target_price=target, spread_at_entry=0.1, lots=1.0, risk_eur=100.0,
        risk_distance=1.0, target_r=1.5, max_holding_bars=12,
        session_landmark_context=context, status=PaperTradeStatus.TARGET,
        exit_at=signal + timedelta(minutes=10), exit_price=target, result_r=1.5,
        pnl_eur=150.0, bars_held=2,
    )


def test_contract_is_preregistered_without_new_numeric_threshold() -> None:
    assert HYPOTHESIS_ID == "recover_rejected_clear_path_to_existing_target_v1"
    assert MIN_SELECTED_OBSERVATIONS == 20


def test_buy_is_rejected_when_favorable_landmark_blocks_before_target() -> None:
    ctx = SessionLandmarkContext(at=NOW, asia_high=101.0, previous_day_high=103.0)
    ok, landmark = clear_path_to_existing_target(trade(Side.BUY, target=101.5, context=ctx))
    assert ok is False
    assert landmark == "asia_high"


def test_buy_is_selected_when_nearest_favorable_landmark_is_at_or_beyond_target() -> None:
    ctx = SessionLandmarkContext(at=NOW, asia_high=101.5, previous_day_high=103.0)
    ok, landmark = clear_path_to_existing_target(trade(Side.BUY, target=101.5, context=ctx))
    assert ok is True
    assert landmark == "asia_high"


def test_sell_is_selected_when_nearest_favorable_landmark_is_beyond_target() -> None:
    ctx = SessionLandmarkContext(at=NOW, asia_low=98.0, previous_day_low=97.0)
    ok, landmark = clear_path_to_existing_target(trade(Side.SELL, target=98.5, context=ctx))
    assert ok is True
    assert landmark == "asia_low"
