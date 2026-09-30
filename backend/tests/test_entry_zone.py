from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

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
from app.domain.trading import Side
from app.services.entry_zone import _stop_for, build_entry_zone
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
