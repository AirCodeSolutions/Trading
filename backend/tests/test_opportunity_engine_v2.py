from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.opportunity_state import OpportunityState, OpportunityStateEvent
from app.domain.regime import MarketRegime
from app.domain.trading import Side
from app.services.opportunity_engine_v2 import (
    _pullback_phase,
    _trigger_candidate,
    build_opportunity_state,
    transition_opportunity_state,
)

AT = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


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


def test_valid_transitions_have_explicit_closed_bar_provenance() -> None:
    state, setup = transition_opportunity_state(
        OpportunityState.NONE,
        OpportunityStateEvent.SETUP_DETECTED,
        at=AT,
        source_closed_at=AT - timedelta(minutes=5),
        reason="setup",
    )
    state, armed = transition_opportunity_state(
        state,
        OpportunityStateEvent.ARMED,
        at=AT + timedelta(minutes=5),
        source_closed_at=AT,
        reason="armed",
    )
    state, triggered = transition_opportunity_state(
        state,
        OpportunityStateEvent.TRIGGERED,
        at=AT + timedelta(minutes=10),
        source_closed_at=AT + timedelta(minutes=5),
        reason="triggered",
    )
    assert state is OpportunityState.TRIGGERED
    assert [item.at for item in (setup, armed, triggered)] == [
        AT,
        AT + timedelta(minutes=5),
        AT + timedelta(minutes=10),
    ]
    assert [item.source_closed_at for item in (setup, armed, triggered)] == [
        AT - timedelta(minutes=5),
        AT,
        AT + timedelta(minutes=5),
    ]


@pytest.mark.parametrize(
    ("current", "event"),
    [
        (OpportunityState.NONE, OpportunityStateEvent.TRIGGERED),
        (OpportunityState.SETUP, OpportunityStateEvent.TRIGGERED),
        (OpportunityState.TRIGGERED, OpportunityStateEvent.ARMED),
    ],
)
def test_invalid_transitions_are_rejected(
    current: OpportunityState, event: OpportunityStateEvent
) -> None:
    with pytest.raises(ValueError, match="invalid opportunity transition"):
        transition_opportunity_state(current, event, at=AT, source_closed_at=AT, reason="invalid")


@pytest.mark.parametrize(
    "event", [OpportunityStateEvent.INVALIDATED, OpportunityStateEvent.EXPIRED]
)
def test_setup_and_armed_can_end_causally(event: OpportunityStateEvent) -> None:
    for current in (OpportunityState.SETUP, OpportunityState.ARMED):
        state, transition = transition_opportunity_state(
            current, event, at=AT, source_closed_at=AT, reason="closed causal condition"
        )
        assert state in (OpportunityState.INVALIDATED, OpportunityState.EXPIRED)
        assert transition.source_closed_at == AT


def test_open_bar_is_rejected_as_source() -> None:
    with pytest.raises(ValueError, match="source bar close"):
        transition_opportunity_state(
            OpportunityState.NONE,
            OpportunityStateEvent.SETUP_DETECTED,
            at=AT,
            source_closed_at=AT + timedelta(minutes=5),
            reason="not closed",
        )


def _candidate(mechanism: OpportunityMechanism, signal_at: datetime) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=mechanism,
        side=Side.BUY,
        signal_at=signal_at,
        entry_at=signal_at,
        signal_index=30,
        entry_index=31,
        structural_stop=98,
        target_r=1.8,
        max_holding_bars=12,
        reason="V1 trigger",
    )


def test_break_retest_builds_real_setup_armed_triggered_lifecycle() -> None:
    bars_m5, bars_m15 = _bars()
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    phases = iter(
        [(OpportunityStateEvent.SETUP_DETECTED, "breakout")]
        + [(OpportunityStateEvent.ARMED, "retest")] * 17
    )
    with (
        patch("app.services.opportunity_engine_v2._regime_for", return_value=regime),
        patch(
            "app.services.opportunity_engine_v2._break_phase",
            side_effect=lambda *args: next(phases),
        ),
        patch(
            "app.services.opportunity_engine_v2._trigger_candidate",
            side_effect=[None] * 17 + [_candidate(OpportunityMechanism.BREAK_RETEST_REACCEL, AT)],
        ),
    ):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
            evaluated_at=AT + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.TRIGGERED
    assert [item.state for item in snapshot.provenance[-3:]] == [
        OpportunityState.SETUP,
        OpportunityState.ARMED,
        OpportunityState.TRIGGERED,
    ]
    assert snapshot.provenance[-3].at < snapshot.provenance[-2].at < snapshot.provenance[-1].at


def test_pullback_setup_can_be_invalidated_without_trigger() -> None:
    bars_m5, bars_m15 = _bars()
    directional = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    balanced = SimpleNamespace(regime=MarketRegime.BALANCED, direction=0)
    regimes = iter([directional] * 34 + [balanced])
    phases = iter(
        [(None, "")] * 33 + [(OpportunityStateEvent.SETUP_DETECTED, "first pullback"), (None, "")]
    )
    with (
        patch(
            "app.services.opportunity_engine_v2._regime_for",
            side_effect=lambda *args: next(regimes),
        ),
        patch(
            "app.services.opportunity_engine_v2._pullback_phase",
            side_effect=lambda *args: next(phases),
        ),
        patch("app.services.opportunity_engine_v2._trigger_candidate", return_value=None),
    ):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
            evaluated_at=AT + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.INVALIDATED


def test_setup_can_expire_on_the_bar_ending_its_native_window() -> None:
    bars_m5, bars_m15 = _bars()
    bars_m5 = bars_m5[:30]
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    phases = iter([(None, "")] * 7 + [(OpportunityStateEvent.SETUP_DETECTED, "breakout")] + [(None, "")] * 4)
    with (
        patch("app.services.opportunity_engine_v2._regime_for", return_value=regime),
        patch(
            "app.services.opportunity_engine_v2._break_phase",
            side_effect=lambda *args: next(phases),
        ),
        patch("app.services.opportunity_engine_v2._trigger_candidate", return_value=None),
    ):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
            evaluated_at=AT,
        )
    assert snapshot.state is OpportunityState.EXPIRED


def test_future_bar_cannot_create_a_state() -> None:
    bars_m5, bars_m15 = _bars()
    with patch("app.services.opportunity_engine_v2._regime_timeline", return_value=([], [])):
        snapshot = build_opportunity_state(
            symbol="XAUUSD",
            bars_m5=bars_m5,
            bars_m15=bars_m15,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
            evaluated_at=AT,
        )
    assert snapshot.state is OpportunityState.NONE


def test_v2_trigger_inspection_never_receives_a_synthetic_future_bar() -> None:
    bars_m5, _ = _bars()
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    atr = [1.0] * len(bars_m5)
    with patch("app.services.opportunity_engine_v2.inspect_break_retest_trigger", return_value=None) as inspect:
        _trigger_candidate(
            bars_m5, atr, len(bars_m5) - 1,
            OpportunityMechanism.BREAK_RETEST_REACCEL, regime,
        )
    inspected_bars = inspect.call_args.args[0]
    assert inspected_bars[-1].timestamp == bars_m5[-1].timestamp
    assert max(bar.timestamp for bar in inspected_bars) <= bars_m5[-1].timestamp


def test_api_snapshot_serializes_and_has_no_broker_authority() -> None:
    snapshot = build_opportunity_state(
        symbol="XAUUSD",
        bars_m5=[],
        bars_m15=[],
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        evaluated_at=AT,
    )
    payload = snapshot.model_dump(mode="json")
    assert payload["state"] == "none"
    assert "execution_proposal" not in payload
    assert "command" not in payload


def _pullback_bars(first: str, second: str, confirmation: str | None = None) -> list[MarketBar]:
    bars, _ = _bars()
    def set_bar(index: int, open_: float, close: float, high: float, low: float) -> None:
        bars[index] = bars[index].model_copy(update={
            "open": open_, "close": close, "high": high, "low": low,
        })
    set_bar(25, 100.0, 99.0, 100.2, 98.8)
    set_bar(26, 99.0, 98.0, 99.2, 97.8)
    if confirmation == "valid":
        set_bar(27, 98.0, 100.0, 100.5, 97.9)
    elif confirmation == "invalid":
        set_bar(27, 98.0, 98.5, 99.0, 97.9)
    elif confirmation == "third_countertrend":
        set_bar(27, 98.0, 97.0, 98.2, 96.8)
    return bars


def test_pullback_phase_uses_current_close_and_previous_bar() -> None:
    bars = _pullback_bars("counter", "counter")
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    setup, _ = _pullback_phase(bars, 25, regime)
    armed, _ = _pullback_phase(bars, 26, regime)
    assert setup is OpportunityStateEvent.SETUP_DETECTED
    assert armed is OpportunityStateEvent.ARMED


def test_real_pullback_lifecycle_has_exact_setup_armed_trigger_timestamps() -> None:
    bars = _pullback_bars("counter", "counter", "valid")
    _, m15 = _bars()
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    with patch("app.services.opportunity_engine_v2._regime_for", return_value=regime):
        snapshot = build_opportunity_state(
            symbol="XAUUSD", bars_m5=bars[:28], bars_m15=m15,
            mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
            evaluated_at=bars[27].timestamp + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.TRIGGERED
    assert [item.state for item in snapshot.provenance[-3:]] == [
        OpportunityState.SETUP, OpportunityState.ARMED, OpportunityState.TRIGGERED
    ]
    assert [item.at for item in snapshot.provenance[-3:]] == [
        bars[25].timestamp + timedelta(minutes=5),
        bars[26].timestamp + timedelta(minutes=5),
        bars[27].timestamp + timedelta(minutes=5),
    ]
    assert snapshot.first_seen_at == bars[25].timestamp + timedelta(minutes=5)


def test_invalid_pullback_confirmation_expires_current_lifecycle() -> None:
    bars = _pullback_bars("counter", "counter", "invalid")
    _, m15 = _bars()
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    with patch("app.services.opportunity_engine_v2._regime_for", return_value=regime):
        snapshot = build_opportunity_state(
            symbol="XAUUSD", bars_m5=bars[:28], bars_m15=m15,
            mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
            evaluated_at=bars[27].timestamp + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.EXPIRED


def test_third_countertrend_rolls_to_a_new_pullback_lifecycle() -> None:
    bars = _pullback_bars("counter", "counter", "third_countertrend")
    _, m15 = _bars()
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    with patch("app.services.opportunity_engine_v2._regime_for", return_value=regime):
        snapshot = build_opportunity_state(
            symbol="XAUUSD", bars_m5=bars[:28], bars_m15=m15,
            mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
            evaluated_at=bars[27].timestamp + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.ARMED
    assert snapshot.first_seen_at == bars[26].timestamp + timedelta(minutes=5)


def test_real_break_retest_lifecycle_uses_shared_trigger_without_future_bars() -> None:
    bars, m15 = _bars()
    def update(index: int, open_: float, high: float, low: float, close: float) -> None:
        bars[index] = bars[index].model_copy(update={
            "open": open_, "high": high, "low": low, "close": close,
        })
    update(22, 100.0, 102.2, 99.8, 102.0)
    update(23, 102.0, 102.3, 101.8, 102.1)
    update(24, 102.1, 102.2, 100.9, 100.5)
    update(25, 100.5, 102.2, 100.9, 101.8)
    regime = SimpleNamespace(regime=MarketRegime.DIRECTIONAL, direction=1)
    with patch("app.services.opportunity_engine_v2._regime_for", return_value=regime):
        snapshot = build_opportunity_state(
            symbol="XAUUSD", bars_m5=bars[:26], bars_m15=m15,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
            evaluated_at=bars[25].timestamp + timedelta(minutes=5),
        )
    assert snapshot.state is OpportunityState.TRIGGERED
    assert [item.state for item in snapshot.provenance[-3:]] == [
        OpportunityState.SETUP, OpportunityState.ARMED, OpportunityState.TRIGGERED
    ]
    assert snapshot.provenance[-3].at < snapshot.provenance[-2].at <= snapshot.provenance[-1].at
