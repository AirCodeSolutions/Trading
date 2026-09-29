from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.opportunity_state import OpportunityState, OpportunityStateEvent
from app.domain.trading import Side
from app.services.opportunity_engine_v2 import (
    build_opportunity_state,
    transition_opportunity_state,
)

AT = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def _bar(timestamp: datetime, close: float = 100.0) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=timestamp,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
    )


def _bars() -> tuple[list[MarketBar], list[MarketBar]]:
    m5 = [_bar(AT - timedelta(minutes=5 * index)) for index in range(35, -1, -1)]
    m15 = [
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M15,
            timestamp=AT - timedelta(minutes=15 * index),
            open=100,
            high=101,
            low=99,
            close=100,
        )
        for index in range(55, -1, -1)
    ]
    return m5, m15


def test_valid_opportunity_state_transitions_are_explicit() -> None:
    state, setup = transition_opportunity_state(
        OpportunityState.NONE,
        OpportunityStateEvent.SETUP_DETECTED,
        at=AT,
        source_bar_at=AT - timedelta(minutes=5),
        reason="setup",
    )
    assert state is OpportunityState.SETUP
    state, armed = transition_opportunity_state(
        state,
        OpportunityStateEvent.ARMED,
        at=AT + timedelta(minutes=5),
        source_bar_at=AT,
        reason="armed",
    )
    assert state is OpportunityState.ARMED
    state, triggered = transition_opportunity_state(
        state,
        OpportunityStateEvent.TRIGGERED,
        at=AT + timedelta(minutes=10),
        source_bar_at=AT + timedelta(minutes=5),
        reason="triggered",
    )
    assert state is OpportunityState.TRIGGERED
    assert [setup.state, armed.state, triggered.state] == [
        OpportunityState.SETUP,
        OpportunityState.ARMED,
        OpportunityState.TRIGGERED,
    ]


@pytest.mark.parametrize(
    ("current", "event"),
    [
        (OpportunityState.NONE, OpportunityState.TRIGGERED),
        (OpportunityState.SETUP, OpportunityState.TRIGGERED),
        (OpportunityState.TRIGGERED, OpportunityState.ARMED),
    ],
)
def test_invalid_transitions_are_rejected(
    current: OpportunityState, event: OpportunityStateEvent
) -> None:
    with pytest.raises(ValueError, match="invalid opportunity transition"):
        transition_opportunity_state(
            current,
            event,
            at=AT,
            source_bar_at=AT,
            reason="invalid",
        )


@pytest.mark.parametrize("event", [OpportunityStateEvent.INVALIDATED, OpportunityStateEvent.EXPIRED])
def test_setup_and_armed_can_invalidate_or_expire(event: OpportunityStateEvent) -> None:
    for current in (OpportunityState.SETUP, OpportunityState.ARMED):
        state, transition = transition_opportunity_state(
            current,
            event,
            at=AT,
            source_bar_at=AT,
            reason="closed causal condition",
        )
        assert state in (OpportunityState.INVALIDATED, OpportunityState.EXPIRED)
        assert transition.reason == "closed causal condition"


def test_future_bar_cannot_drive_a_transition() -> None:
    with pytest.raises(ValueError, match="decision cannot precede"):
        transition_opportunity_state(
            OpportunityState.NONE,
            OpportunityStateEvent.SETUP_DETECTED,
            at=AT,
            source_bar_at=AT + timedelta(minutes=5),
            reason="future bar",
        )


def test_existing_break_retest_candidate_is_exposed_as_triggered_without_execution_authority() -> None:
    bars_m5, bars_m15 = _bars()
    latest_signal_at = bars_m5[-1].timestamp + timedelta(minutes=5)
    candidate = OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=Side.BUY,
        signal_at=latest_signal_at,
        entry_at=latest_signal_at,
        signal_index=len(bars_m5) - 1,
        entry_index=len(bars_m5) - 1,
        structural_stop=98.0,
        target_r=1.8,
        max_holding_bars=12,
        reason="closed-bar break/retest trigger",
    )
    with patch(
        "app.services.opportunity_engine_v2.generate_candidates",
        return_value=[candidate],
    ):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
            evaluated_at=AT,
        )
    assert snapshot.state is OpportunityState.TRIGGERED
    assert snapshot.side is Side.BUY
    assert snapshot.provenance[-1].state is OpportunityState.TRIGGERED
    assert snapshot.model_dump()["state"] is OpportunityState.TRIGGERED
    assert not hasattr(snapshot, "execution_proposal")


def test_setup_is_causal_and_non_broker() -> None:
    bars_m5, bars_m15 = _bars()
    candidate = OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        side=Side.SELL,
        signal_at=bars_m5[-2].timestamp + timedelta(minutes=5),
        entry_at=bars_m5[-2].timestamp + timedelta(minutes=5),
        signal_index=len(bars_m5) - 2,
        entry_index=len(bars_m5) - 2,
        structural_stop=102.0,
        target_r=1.5,
        max_holding_bars=12,
        reason="closed-bar setup",
    )
    with patch(
        "app.services.opportunity_engine_v2.generate_candidates",
        return_value=[candidate],
    ):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
            evaluated_at=AT,
        )
    assert snapshot.state is OpportunityState.ARMED
    assert snapshot.model_dump_json()
    assert snapshot.provenance[-1].source_bar_at <= snapshot.updated_at


def test_opportunity_state_api_serializes_read_only_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    bars_m5, bars_m15 = _bars()
    monkeypatch.setattr(main.settings, "session_watch_symbols", ["XAUUSD"])
    monkeypatch.setattr(main, "_mt4_files_dir", lambda: AT)
    monkeypatch.setattr(main, "load_closed_market_bars", lambda *args, **kwargs: (
        bars_m5 if kwargs["timeframe"] is Timeframe.M5 else bars_m15
    ))
    payload = [snapshot.model_dump(mode="json") for snapshot in main.opportunity_states_v2()]
    assert {item["mechanism"] for item in payload} == {
        "break_retest_reaccel",
        "directional_pullback_resumption",
    }
    assert all("age_seconds" in item for item in payload)
