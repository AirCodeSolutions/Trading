from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.domain.broker import BrokerSymbolSpec
from app.domain.entry_zone import EntryZoneState
from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
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
