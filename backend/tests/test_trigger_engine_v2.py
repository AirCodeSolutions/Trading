from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import (
    OpportunityState,
    OpportunityStateEvent,
    OpportunityStateSnapshot,
    OpportunityStateTransition,
)
from app.domain.trading import Side
from app.domain.trigger_engine import TriggerEngineState
from app.domain.xau_microbar import XauMicrobarM1
from app.services.trigger_engine_v2 import build_trigger_engine_snapshot

START = datetime(2026, 9, 30, 10, tzinfo=ZoneInfo("Europe/Athens"))


def row(at: datetime, *, side: Side = Side.BUY, close: float = 106.0, up: int = 3, down: int = 1) -> XauMicrobarM1:
    if side is Side.BUY:
        open_price, bid_close, ask_close = close - 0.3, close, close + 0.01
    else:
        open_price, bid_close, ask_close = close + 0.3, close - 0.01, close
    return XauMicrobarM1(
        minute_at=at, first_quote_at=at, last_quote_at=at + timedelta(seconds=59),
        bid_open=open_price, bid_high=max(open_price, bid_close) + 0.1, bid_low=min(open_price, bid_close) - 0.1, bid_close=bid_close,
        ask_open=open_price + 0.01, ask_high=max(open_price, ask_close) + 0.1, ask_low=min(open_price, ask_close) - 0.1, ask_close=ask_close,
        mid_open=open_price + 0.005, mid_high=max(open_price, close) + 0.1, mid_low=min(open_price, close) - 0.1, mid_close=close,
        spread_open=0.01, spread_high=0.01, spread_low=0.01, spread_close=0.01, spread_sum=0.01,
        quote_count=1, mid_up_ticks=up, mid_down_ticks=down,
    )


def armed_snapshot(side: Side, *, triggered: bool = False) -> OpportunityStateSnapshot:
    armed_at = START + timedelta(minutes=10)
    armed = OpportunityStateTransition(state=OpportunityState.ARMED, at=armed_at, source_closed_at=armed_at, event=OpportunityStateEvent.ARMED, reason="armed")
    provenance = [armed]
    state = OpportunityState.ARMED
    triggered_at = None
    if triggered:
        triggered_at = START + timedelta(minutes=14)
        provenance.append(OpportunityStateTransition(state=OpportunityState.TRIGGERED, at=triggered_at, source_closed_at=triggered_at, event=OpportunityStateEvent.TRIGGERED, reason="v1"))
        state = OpportunityState.TRIGGERED
    return OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION, side=side, state=state, updated_at=triggered_at or armed_at, triggered_at=triggered_at, provenance=provenance, reason="test")


def pullback_bars() -> list[MarketBar]:
    return [
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=START, open=100, high=101, low=99, close=100.5),
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=START + timedelta(minutes=5), open=100.5, high=101, low=100, close=100.8),
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=START + timedelta(minutes=10), open=101, high=103, low=100.5, close=102),
    ]


@pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
def test_armed_pullback_uses_first_causal_m1_and_side_price(side):
    snapshot = armed_snapshot(side)
    bars = pullback_bars()
    rows = [row(START + timedelta(minutes=11), side=side, close=104, up=4, down=1)]
    if side is Side.SELL:
        rows = [row(START + timedelta(minutes=11), side=side, close=99, up=1, down=4)]
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=rows, evaluated_at=START + timedelta(minutes=12), bars_m5=bars)
    assert result.state is TriggerEngineState.EARLY_TRIGGERED
    assert result.early_trigger_source_closed_at == START + timedelta(minutes=12)
    assert result.early_trigger_price == (rows[0].ask_close if side is Side.BUY else rows[0].bid_close)
    assert result.directional_tick_samples == 5
    assert result.side_aligned_tick_imbalance == pytest.approx(0.6)


def test_future_and_open_m1_are_never_used():
    snapshot = armed_snapshot(Side.BUY)
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[row(START + timedelta(minutes=12), close=110)], evaluated_at=START + timedelta(minutes=12, seconds=30), bars_m5=pullback_bars())
    assert result.state is TriggerEngineState.M1_UNAVAILABLE
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[row(START + timedelta(minutes=11), close=104)], evaluated_at=START + timedelta(minutes=12), bars_m5=pullback_bars())
    assert result.state is TriggerEngineState.EARLY_TRIGGERED


def test_pullback_m1_stale_is_explicit():
    snapshot = armed_snapshot(Side.BUY)
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[row(START + timedelta(minutes=11), close=104)], evaluated_at=START + timedelta(minutes=40), bars_m5=pullback_bars())
    assert result.state is TriggerEngineState.WAITING
    assert result.m1_status == "stale"


def test_zero_tick_pressure_is_unavailable_without_veto():
    snapshot = armed_snapshot(Side.BUY)
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[row(START + timedelta(minutes=11), close=104, up=0, down=0)], evaluated_at=START + timedelta(minutes=12), bars_m5=pullback_bars())
    assert result.state is TriggerEngineState.EARLY_TRIGGERED
    assert result.directional_tick_samples == 0
    assert result.raw_tick_imbalance is None


def test_armed_without_m1_is_explicitly_unavailable():
    result = build_trigger_engine_snapshot(snapshot=armed_snapshot(Side.BUY), microbars=[], evaluated_at=START + timedelta(minutes=12), bars_m5=pullback_bars())
    assert result.state is TriggerEngineState.M1_UNAVAILABLE
    assert not result.m1_available


def test_v1_reference_and_positive_lead_are_exposed():
    snapshot = armed_snapshot(Side.BUY, triggered=True)
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[row(START + timedelta(minutes=11), close=104)], evaluated_at=START + timedelta(minutes=15), bars_m5=pullback_bars(), atr_reference=2, v1_reference_price=106.5)
    assert result.state is TriggerEngineState.EARLY_TRIGGERED
    assert result.v1_trigger_source_closed_at == START + timedelta(minutes=14)
    assert result.lead_minutes == pytest.approx(2.0)
    assert result.move_saved_vs_v1_atr > 0


def test_non_representative_mechanism_is_not_applicable():
    snapshot = armed_snapshot(Side.BUY).model_copy(update={"mechanism": OpportunityMechanism.FAILED_AUCTION_REVERSAL})
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[], evaluated_at=START + timedelta(minutes=12))
    assert result.state is TriggerEngineState.NOT_APPLICABLE


def test_first_valid_m1_is_kept_and_input_order_is_irrelevant():
    snapshot = armed_snapshot(Side.BUY)
    invalid = row(START + timedelta(minutes=11), close=102).model_copy(update={"mid_open": 102.2})
    first = row(START + timedelta(minutes=12), close=104)
    later = row(START + timedelta(minutes=13), close=105)
    ordered = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[invalid, first, later], evaluated_at=START + timedelta(minutes=14), bars_m5=pullback_bars())
    shuffled = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[later, invalid, first], evaluated_at=START + timedelta(minutes=14), bars_m5=pullback_bars())
    assert ordered.early_trigger_at == START + timedelta(minutes=13)
    assert shuffled.early_trigger_at == ordered.early_trigger_at
    assert ordered.early_trigger_price == first.ask_close


def break_bars() -> list[MarketBar]:
    bars = []
    for index in range(18):
        at = START + timedelta(minutes=index * 5)
        close = 101 if index >= 15 else 100
        bars.append(MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=at, open=100, high=max(100.2, close), low=99.8, close=close))
    return bars


def break_snapshot(side: Side) -> OpportunityStateSnapshot:
    armed_at = START + timedelta(minutes=90)
    transition = OpportunityStateTransition(state=OpportunityState.ARMED, at=armed_at, source_closed_at=armed_at, event=OpportunityStateEvent.ARMED, reason="armed")
    return OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL, side=side, state=OpportunityState.ARMED, updated_at=armed_at, provenance=[transition], reason="test")


def test_break_retest_early_trigger_uses_close_location():
    valid = row(START + timedelta(minutes=91), close=102)
    result = build_trigger_engine_snapshot(snapshot=break_snapshot(Side.BUY), microbars=[valid], evaluated_at=START + timedelta(minutes=92), bars_m5=break_bars())
    assert result.state is TriggerEngineState.EARLY_TRIGGERED
    low_location = valid.model_copy(update={"mid_low": 99.0, "mid_high": 105.0, "ask_low": 99.01, "ask_high": 105.01})
    rejected = build_trigger_engine_snapshot(snapshot=break_snapshot(Side.BUY), microbars=[low_location], evaluated_at=START + timedelta(minutes=92), bars_m5=break_bars())
    assert rejected.state is TriggerEngineState.WAITING


def test_pullback_sell_move_saved_is_side_aligned():
    snapshot = armed_snapshot(Side.SELL, triggered=True)
    sell_row = row(START + timedelta(minutes=11), side=Side.SELL, close=99, up=1, down=4)
    result = build_trigger_engine_snapshot(snapshot=snapshot, microbars=[sell_row], evaluated_at=START + timedelta(minutes=15), bars_m5=pullback_bars(), atr_reference=2, v1_reference_price=98)
    assert result.state is TriggerEngineState.EARLY_TRIGGERED
    assert result.early_trigger_price == sell_row.bid_close
    assert result.move_saved_vs_v1_atr == pytest.approx((sell_row.bid_close - 98) / 2)


def test_trigger_endpoint_returns_five_assets_and_two_mechanisms(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app import main

    monkeypatch.setattr(main, "_mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(main, "load_closed_market_bars", lambda *args, **kwargs: [])
    response = TestClient(main.app).get("/api/v1/triggers/v2")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 10
    assert {item["symbol"] for item in payload} == {"BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"}
    assert not any(key in row for row in payload for key in ("order", "command", "proposal", "approval", "execution"))
