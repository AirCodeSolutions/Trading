from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.entry_zone import EntryZoneState
from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateV2
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import (
    OpportunityState,
    OpportunityStateEvent,
    OpportunityStateSnapshot,
    OpportunityStateTransition,
)
from app.domain.runtime_capital import RuntimeCapitalSnapshot, RuntimeCapitalSource
from app.domain.session_landmark import SessionLandmarkContext
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.entry_zone import _landmark, _stop_for, build_entry_zone
from app.services.opportunity_triggers import TriggerInspection

NOW = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Europe/Athens"))


def market_state() -> MarketStateV2:
    return MarketStateV2(symbol="XAUUSD", evaluated_at=NOW, m5_freshness="fresh", m15_freshness="fresh", atr_m5=1.0)


@pytest.mark.parametrize("state", [OpportunityState.NONE, OpportunityState.SETUP, OpportunityState.ARMED, OpportunityState.INVALIDATED, OpportunityState.EXPIRED])
def test_entry_zone_is_not_applicable_before_trigger(state):
    snapshot = OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL, state=state, updated_at=NOW, reason="test")
    zone = build_entry_zone(snapshot=snapshot, market_state=market_state(), bars_m5=[], bars_m15=[], quote=None, spec=None, capital=RuntimeCapitalSnapshot(source=RuntimeCapitalSource.UNAVAILABLE))
    assert zone.state is EntryZoneState.NOT_APPLICABLE
    assert zone.current_entry is None
    assert zone.model_dump().get("order") is None


def test_stop_geometry_matches_shadow_rules_for_both_sides():
    buy = TriggerInspection(Side.BUY, 95, 1.8, 18, 4, None, None, None, None, "test")
    sell = TriggerInspection(Side.SELL, 105, 1.8, 18, 4, None, None, None, None, "test")
    assert _stop_for(buy, 100, 1, 2, OpportunityMechanism.BREAK_RETEST_REACCEL) == 95
    assert _stop_for(sell, 100, 1, 2, OpportunityMechanism.BREAK_RETEST_REACCEL) == 106
    assert _stop_for(buy, 100, 1, 2, OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION) == 95
    assert _stop_for(sell, 100, 1, 2, OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION) == 106


def test_entry_zone_api_returns_two_descriptive_states_per_asset(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main, "_mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(main, "read_live_market_quotes", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "load_closed_market_bars", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "list_mt4_symbol_specs", lambda *args, **kwargs: {})
    monkeypatch.setattr(main, "resolve_demo_sizing_capital", lambda *args, **kwargs: RuntimeCapitalSnapshot(source=RuntimeCapitalSource.UNAVAILABLE))
    response = TestClient(main.app).get("/api/v1/entry-zones/v2")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 10
    assert {row["symbol"] for row in payload} == {"BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"}
    assert all(row["state"] == "not_applicable" for row in payload)
    assert all(not any(key in row for key in ("order", "command", "proposal", "approved_for_demo")) for row in payload)


def test_unsupported_mechanism_is_not_routed_to_pullback():
    snapshot = OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL, state=OpportunityState.TRIGGERED, triggered_at=NOW, updated_at=NOW, reason="test")
    zone = build_entry_zone(snapshot=snapshot, market_state=market_state(), bars_m5=[], bars_m15=[], quote=None, spec=None, capital=RuntimeCapitalSnapshot(source=RuntimeCapitalSource.UNAVAILABLE))
    assert zone.state is EntryZoneState.NOT_APPLICABLE
    assert zone.reason == "mechanism not supported by Entry Zone V2"


def test_research_capital_is_rejected_even_when_non_null(monkeypatch):
    transition = OpportunityStateTransition(state=OpportunityState.TRIGGERED, at=NOW, source_closed_at=NOW, event=OpportunityStateEvent.TRIGGERED, reason="test")
    snapshot = OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL, state=OpportunityState.TRIGGERED, triggered_at=NOW, updated_at=NOW, reason="test", provenance=[transition])
    monkeypatch.setattr("app.services.entry_zone._trigger_for", lambda *args: (None, None, None, []))
    quote = LiveMarketQuote(symbol="XAUUSD", as_of=NOW, bid=100, ask=101, mid=100.5, spread=1, spread_pct=1, digits=2, age_seconds=0, status=MarketFeedStatus.LIVE)
    spec = BrokerSymbolSpec(symbol="XAUUSD", bid=100, ask=101, tick_size=1, tick_value=1, min_lot=0.1, max_lot=10, lot_step=0.1)
    zone = build_entry_zone(snapshot=snapshot, market_state=market_state(), bars_m5=[], bars_m15=[], quote=quote, spec=spec, capital=RuntimeCapitalSnapshot(capital_eur=400, source=RuntimeCapitalSource.RESEARCH_FALLBACK, is_demo=True))
    assert zone.state is EntryZoneState.DATA_UNAVAILABLE
    assert "research fallback" in zone.reason


def test_trigger_provenance_keeps_trigger_and_source_close_distinct():
    from app.domain.opportunity_state import OpportunityStateEvent, OpportunityStateTransition
    trigger_at = NOW
    source_closed_at = NOW.replace(minute=55)
    snapshot = OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL, state=OpportunityState.TRIGGERED, triggered_at=trigger_at, updated_at=NOW, reason="test", provenance=[OpportunityStateTransition(state=OpportunityState.TRIGGERED, at=trigger_at, source_closed_at=source_closed_at, event=OpportunityStateEvent.TRIGGERED, reason="test")])
    assert snapshot.triggered_at != snapshot.provenance[0].source_closed_at


def _real_pullback_case():
    start = datetime(2026, 9, 30, 8, tzinfo=ZoneInfo("Europe/Athens"))
    m15 = []
    price = 100.0
    for index in range(55):
        close = price + 0.2
        m15.append(MarketBar(symbol="XAUUSD", timeframe=Timeframe.M15, timestamp=start + timedelta(minutes=index * 15), open=price, high=close + 0.1, low=price - 0.1, close=close))
        price = close
    m5 = []
    for index in range(27):
        value = 105 + index * 0.05
        m5.append(MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=start + timedelta(minutes=750 + index * 5), open=value, high=value + 0.2, low=value - 0.2, close=value + 0.05))
    m5.extend([
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=start + timedelta(minutes=885), open=106.35, high=106.4, low=105.1, close=105.5),
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=start + timedelta(minutes=890), open=105.5, high=105.6, low=104.8, close=105.0),
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=start + timedelta(minutes=895), open=105.0, high=106.6, low=104.9, close=106.5),
    ])
    trigger_at = start + timedelta(minutes=900)
    transition = OpportunityStateTransition(state=OpportunityState.TRIGGERED, at=trigger_at, source_closed_at=trigger_at, event=OpportunityStateEvent.TRIGGERED, reason="real trigger")
    snapshot = OpportunityStateSnapshot(symbol="XAUUSD", mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION, state=OpportunityState.TRIGGERED, triggered_at=trigger_at, updated_at=trigger_at, reason="real trigger", provenance=[transition])
    state = MarketStateV2(symbol="XAUUSD", evaluated_at=trigger_at + timedelta(minutes=5), m5_freshness="fresh", m15_freshness="fresh", atr_m5=1.0)
    spec = BrokerSymbolSpec(symbol="XAUUSD", bid=106.5, ask=106.51, tick_size=0.01, tick_value=1, min_lot=0.1, max_lot=10, lot_step=0.1)
    quote = LiveMarketQuote(symbol="XAUUSD", as_of=trigger_at + timedelta(minutes=5), bid=106.5, ask=106.51, mid=106.505, spread=0.01, spread_pct=0.01, digits=2, age_seconds=0, status=MarketFeedStatus.LIVE)
    capital = RuntimeCapitalSnapshot(capital_eur=10000, source=RuntimeCapitalSource.BROKER_EQUITY, is_demo=True)
    return snapshot, state, m5, m15, quote, spec, capital


def test_real_trigger_reaches_currently_executable_without_broker_action():
    case = _real_pullback_case()
    zone = build_entry_zone(snapshot=case[0], market_state=case[1], bars_m5=case[2], bars_m15=case[3], quote=case[4], spec=case[5], capital=case[6])
    assert zone.state is EntryZoneState.CURRENTLY_EXECUTABLE
    assert zone.current_entry is not None and zone.structural_stop is not None
    assert zone.sizing is not None and zone.sizing.lots is not None and zone.sizing.lots > 0
    assert zone.sizing.lots <= 5
    assert zone.trigger_source_closed_at == case[0].provenance[0].source_closed_at
    assert zone.post_trigger_chase_atr is not None


@pytest.mark.parametrize("quote_mode", ["stale", "future", "absent"])
def test_real_trigger_requires_fresh_quote(quote_mode):
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    if quote_mode == "stale":
        quote = quote.model_copy(update={"status": MarketFeedStatus.STALE})
    elif quote_mode == "future":
        quote = quote.model_copy(update={"as_of": state.evaluated_at + timedelta(minutes=1)})
    else:
        quote = None
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.DATA_UNAVAILABLE

@pytest.mark.parametrize(
    "capital",
    [
        RuntimeCapitalSnapshot(capital_eur=10000, source=RuntimeCapitalSource.BROKER_BALANCE, is_demo=True),
        RuntimeCapitalSnapshot(capital_eur=400, source=RuntimeCapitalSource.RESEARCH_FALLBACK, is_demo=True),
        RuntimeCapitalSnapshot(capital_eur=10000, source=RuntimeCapitalSource.BROKER_EQUITY, is_demo=False),
        RuntimeCapitalSnapshot(source=RuntimeCapitalSource.UNAVAILABLE),
    ],
)
def test_real_trigger_accepts_only_demo_broker_capital(capital):
    case = _real_pullback_case()
    zone = build_entry_zone(snapshot=case[0], market_state=case[1], bars_m5=case[2], bars_m15=case[3], quote=case[4], spec=case[5], capital=capital)
    if capital.source is RuntimeCapitalSource.BROKER_BALANCE:
        assert zone.state is EntryZoneState.CURRENTLY_EXECUTABLE
    else:
        assert zone.state is EntryZoneState.DATA_UNAVAILABLE


def test_real_pullback_band_is_numeric_and_trigger_provenance_is_preserved():
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    source = snapshot.provenance[0].source_closed_at - timedelta(minutes=5)
    snapshot = snapshot.model_copy(update={"provenance": [snapshot.provenance[0].model_copy(update={"source_closed_at": source})]})
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.CURRENTLY_EXECUTABLE
    assert zone.trigger_at == snapshot.provenance[0].at
    assert zone.trigger_source_closed_at == source
    assert zone.entry_zone_low is not None and zone.entry_zone_high is not None
    assert zone.entry_zone_low <= zone.entry_zone_high
    assert zone.minimum_stop_distance_for_spread <= zone.maximum_stop_distance_for_min_lot_budget


def test_shared_stop_geometry_covers_asia_sweep_sides():
    from app.services.stop_geometry import resolve_trigger_structural_stop
    assert resolve_trigger_structural_stop(OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL, Side.BUY, 95, 100, 2, 1) == 95
    assert resolve_trigger_structural_stop(OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL, Side.SELL, 105, 100, 2, 1) == 106


def test_waiting_price_when_current_price_is_too_close_but_band_is_viable():
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    quote = quote.model_copy(update={"bid": 104.70, "ask": 104.80, "mid": 104.75})
    spec = spec.model_copy(update={"bid": quote.bid, "ask": quote.ask})
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.WAITING_PRICE
    assert zone.entry_zone_low is not None and zone.entry_zone_high is not None
    assert zone.entry_zone_low <= zone.entry_zone_high
    assert zone.current_entry < zone.entry_zone_low
    assert zone.minimum_stop_distance_for_spread == pytest.approx((quote.ask - quote.bid) / settings.max_spread_to_stop)


def test_waiting_price_when_current_price_is_too_far_but_band_is_viable():
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    quote = quote.model_copy(update={"bid": 116.0, "ask": 116.01, "mid": 116.005})
    spec = spec.model_copy(update={"bid": quote.bid, "ask": quote.ask})
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.WAITING_PRICE
    assert zone.entry_zone_low is not None and zone.entry_zone_high is not None
    assert zone.current_entry > zone.entry_zone_high


def test_margin_rejection_is_economically_blocked_not_waiting_price():
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    spec = spec.model_copy(update={"margin_required": 100_000})
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.ECONOMICALLY_BLOCKED
    assert zone.sizing is not None
    assert zone.sizing.sizing_reason == "estimated margin exceeds capital policy"


def test_spread_limit_is_numeric_and_not_relaxed():
    exact = size_position(__import__("app.domain.broker", fromlist=["PositionSizeRequest"]).PositionSizeRequest(
        spec=BrokerSymbolSpec(symbol="XAUUSD", bid=100, ask=100.15, tick_size=0.01, tick_value=1, min_lot=0.1, max_lot=10, lot_step=0.1),
        entry=100.15, stop=99.15, capital_eur=10000,
    ))
    above = size_position(__import__("app.domain.broker", fromlist=["PositionSizeRequest"]).PositionSizeRequest(
        spec=BrokerSymbolSpec(symbol="XAUUSD", bid=100, ask=100.1501, tick_size=0.01, tick_value=1, min_lot=0.1, max_lot=10, lot_step=0.1),
        entry=100.1501, stop=99.15, capital_eur=10000,
    ))
    assert exact.spread_to_stop == pytest.approx(settings.max_spread_to_stop)
    assert exact.approved
    assert above.spread_to_stop > settings.max_spread_to_stop
    assert not above.approved
    assert above.reason == "spread consumes too much of the stop distance"


def test_pullback_min_lot_budget_and_five_lot_cap_are_reported():
    snapshot, state, m5, m15, quote, spec, _ = _real_pullback_case()
    tiny = RuntimeCapitalSnapshot(capital_eur=1, source=RuntimeCapitalSource.BROKER_EQUITY, is_demo=True)
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=tiny)
    assert zone.sizing is not None
    assert zone.sizing.min_lot_loss_eur > zone.sizing.risk_budget_eur
    assert zone.maximum_stop_distance_for_min_lot_budget < zone.current_stop_distance
    huge = _real_pullback_case()[6].model_copy(update={"capital_eur": 1_000_000})
    capped = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=huge)
    assert capped.sizing is not None and capped.sizing.lots <= settings.max_lots_per_trade <= 5


@pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
def test_landmark_selection_is_side_aligned(side):
    if side is Side.BUY:
        entry = 106.51
        landmarks = SessionLandmarkContext(at=NOW, previous_day_high=110, asia_high=108, london_high_so_far=107)
    else:
        entry = 103.5
        landmarks = SessionLandmarkContext(at=NOW, previous_day_low=99, asia_low=102, london_low_so_far=101)
    state = MarketStateV2(symbol="XAUUSD", evaluated_at=NOW, m5_freshness="fresh", m15_freshness="fresh", atr_m5=1.0, session_context=landmarks)
    landmark_type, landmark_price, distance, distance_atr, room = _landmark(state, side, entry, 1.0)
    assert landmark_type is not None
    assert landmark_price is not None
    if side is Side.BUY:
        assert landmark_type == "london_high_so_far"
        assert landmark_price == 107
    else:
        assert landmark_type == "asia_low"
        assert landmark_price == 102
    assert distance == pytest.approx(abs(landmark_price - entry))
    assert distance_atr == pytest.approx(distance)
    assert room == pytest.approx(distance)


def test_no_favorable_landmark_returns_none():
    state = MarketStateV2(symbol="XAUUSD", evaluated_at=NOW, m5_freshness="fresh", m15_freshness="fresh", atr_m5=1.0, session_context=SessionLandmarkContext(at=NOW, previous_day_low=90, asia_low=91))
    assert _landmark(state, Side.BUY, 100, 1.0) == (None, None, None, None, None)
    assert _landmark(state, Side.SELL, 80, 1.0) == (None, None, None, None, None)


@pytest.mark.parametrize("field", ["quote", "spec"])
def test_wrong_quote_or_spec_symbol_is_unavailable(field):
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    if field == "quote":
        quote = quote.model_copy(update={"symbol": "BTCUSD"})
    else:
        spec = spec.model_copy(update={"symbol": "BTCUSD"})
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.DATA_UNAVAILABLE


@pytest.mark.parametrize("timeframe", [Timeframe.M5, Timeframe.M15])
def test_wrong_bar_symbol_is_unavailable(timeframe):
    snapshot, state, m5, m15, quote, spec, capital = _real_pullback_case()
    bad = MarketBar(symbol="BTCUSD", timeframe=timeframe, timestamp=(m5 if timeframe is Timeframe.M5 else m15)[0].timestamp, open=100, high=101, low=99, close=100)
    if timeframe is Timeframe.M5:
        m5 = [bad, *m5[1:]]
    else:
        m15 = [bad, *m15[1:]]
    zone = build_entry_zone(snapshot=snapshot, market_state=state, bars_m5=m5, bars_m15=m15, quote=quote, spec=spec, capital=capital)
    assert zone.state is EntryZoneState.DATA_UNAVAILABLE
