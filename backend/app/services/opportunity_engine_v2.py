from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import (
    OpportunityState,
    OpportunityStateEvent,
    OpportunityStateSnapshot,
    OpportunityStateTransition,
)
from app.domain.regime import MarketRegime
from app.domain.trading import Side
from app.services.opportunity_strategies import (
    _atr_series,
    _regime_timeline,
)
from app.services.opportunity_triggers import (
    inspect_break_retest_trigger,
    inspect_directional_pullback_trigger,
)

REPRESENTATIVE_MECHANISMS = (
    OpportunityMechanism.BREAK_RETEST_REACCEL,
    OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
)

_ALLOWED = {
    OpportunityState.NONE: {OpportunityState.SETUP},
    OpportunityState.SETUP: {
        OpportunityState.ARMED,
        OpportunityState.INVALIDATED,
        OpportunityState.EXPIRED,
    },
    OpportunityState.ARMED: {
        OpportunityState.TRIGGERED,
        OpportunityState.INVALIDATED,
        OpportunityState.EXPIRED,
    },
}


def transition_opportunity_state(
    current: OpportunityState,
    event: OpportunityStateEvent,
    *,
    at: datetime,
    source_closed_at: datetime,
    reason: str,
) -> tuple[OpportunityState, OpportunityStateTransition]:
    target = {
        OpportunityStateEvent.SETUP_DETECTED: OpportunityState.SETUP,
        OpportunityStateEvent.ARMED: OpportunityState.ARMED,
        OpportunityStateEvent.TRIGGERED: OpportunityState.TRIGGERED,
        OpportunityStateEvent.INVALIDATED: OpportunityState.INVALIDATED,
        OpportunityStateEvent.EXPIRED: OpportunityState.EXPIRED,
    }[event]
    if source_closed_at > at:
        raise ValueError("decision cannot precede source bar close")
    if target not in _ALLOWED.get(current, set()):
        raise ValueError(f"invalid opportunity transition: {current} -> {target}")
    return target, OpportunityStateTransition(
        state=target, at=at, source_closed_at=source_closed_at, event=event, reason=reason
    )


def _closed_at(bar: MarketBar) -> datetime:
    return bar.timestamp + timedelta(minutes=5 if bar.timeframe.value == "M5" else 15)


def _regime_for(
    close_times: Sequence[datetime], regimes: Sequence[object], at: datetime
) -> object | None:
    for close_time, regime in reversed(list(zip(close_times, regimes))):
        if close_time <= at:
            return regime
    return None


def _trigger_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
    mechanism: OpportunityMechanism,
    regime: object,
):
    if mechanism is OpportunityMechanism.BREAK_RETEST_REACCEL:
        return inspect_break_retest_trigger(bars[: index + 1], atr[: index + 1], regime)
    return inspect_directional_pullback_trigger(bars[: index + 1], atr[: index + 1], regime)


def _break_phase(
    bars: Sequence[MarketBar], atr: Sequence[float], index: int, regime: object
) -> tuple[OpportunityStateEvent | None, str]:
    if (
        getattr(regime, "regime", None) is not MarketRegime.DIRECTIONAL
        or getattr(regime, "direction", 0) == 0
        or index < 18
        or atr[index] <= 0
    ):
        return None, "directional context unavailable"
    base = bars[index - 15 : index - 3]
    recent = bars[index - 3 : index]
    level = (
        max(item.high for item in base) if regime.direction > 0 else min(item.low for item in base)
    )
    value = atr[index]
    breakout = (
        max(item.close for item in recent) > level + 0.05 * value
        if regime.direction > 0
        else min(item.close for item in recent) < level - 0.05 * value
    )
    if not breakout:
        return None, "no causal breakout context"
    retest = (
        bars[index].low <= level + 0.30 * value
        if regime.direction > 0
        else bars[index].high >= level - 0.30 * value
    )
    return (
        (OpportunityStateEvent.ARMED, "breakout retest is in progress")
        if retest
        else (OpportunityStateEvent.SETUP_DETECTED, "causal breakout is awaiting retest")
    )


def _pullback_phase(
    bars: Sequence[MarketBar], index: int, regime: object
) -> tuple[OpportunityStateEvent | None, str]:
    if (
        getattr(regime, "regime", None) is not MarketRegime.DIRECTIONAL
        or getattr(regime, "direction", 0) == 0
        or index < 2
    ):
        return None, "no causal pullback context"
    first, second = bars[index - 2], bars[index - 1]
    first_counter = first.close < first.open if regime.direction > 0 else first.close > first.open
    second_counter = (
        second.close < second.open if regime.direction > 0 else second.close > second.open
    )
    if not first_counter:
        return None, "no first counter-trend pullback"
    return (
        (OpportunityStateEvent.ARMED, "two causal pullback bars are closed")
        if second_counter
        else (OpportunityStateEvent.SETUP_DETECTED, "first counter-trend pullback is closed")
    )


def _snapshot_from_events(
    symbol: str,
    mechanism: OpportunityMechanism,
    evaluated_at: datetime,
    events: list[tuple[OpportunityStateEvent, datetime, datetime, str, Side | None]],
) -> OpportunityStateSnapshot:
    state = OpportunityState.NONE
    transitions: list[OpportunityStateTransition] = []
    side = None
    first_seen_at = None
    triggered_at = None
    reason = "no current causal setup"
    for event, at, closed_at, event_reason, event_side in events:
        if event is OpportunityStateEvent.SETUP_DETECTED:
            first_seen_at = at
        state, transition = transition_opportunity_state(
            state, event, at=at, source_closed_at=closed_at, reason=event_reason
        )
        transitions.append(transition)
        side = event_side or side
        reason = event_reason
        if state is OpportunityState.TRIGGERED:
            triggered_at = at
    return OpportunityStateSnapshot(
        symbol=symbol,
        mechanism=mechanism,
        side=side,
        state=state,
        first_seen_at=first_seen_at,
        updated_at=evaluated_at,
        triggered_at=triggered_at,
        invalidation_reason=reason if state is OpportunityState.INVALIDATED else None,
        expiration_reason=reason if state is OpportunityState.EXPIRED else None,
        reason=reason,
        provenance=transitions,
    )


def build_opportunity_state(
    *,
    symbol: str,
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    mechanism: OpportunityMechanism,
    evaluated_at: datetime,
) -> OpportunityStateSnapshot:
    bars_m5 = [bar for bar in bars_m5 if _closed_at(bar) <= evaluated_at]
    bars_m15 = [bar for bar in bars_m15 if _closed_at(bar) <= evaluated_at]
    if mechanism not in REPRESENTATIVE_MECHANISMS or not bars_m5 or not bars_m15:
        return OpportunityStateSnapshot(
            symbol=symbol,
            mechanism=mechanism,
            state=OpportunityState.NONE,
            updated_at=evaluated_at,
            reason="insufficient causal history or unsupported V2 mechanism",
        )
    atr = _atr_series(bars_m5)
    close_times, regimes = _regime_timeline(bars_m15)
    lifecycle: list[tuple[OpportunityStateEvent, datetime, datetime, str, Side | None]] = []
    state = OpportunityState.NONE
    active_index: int | None = None
    for index, bar in enumerate(bars_m5):
        if index < 25:
            continue
        closed_at = _closed_at(bar)
        regime = _regime_for(close_times, regimes, closed_at)
        if regime is None:
            continue
        phase, phase_reason = (
            _break_phase(bars_m5, atr, index, regime)
            if mechanism is OpportunityMechanism.BREAK_RETEST_REACCEL
            else _pullback_phase(bars_m5, index, regime)
        )
        trigger = _trigger_candidate(bars_m5, atr, index, mechanism, regime)
        side = (
            Side.BUY
            if getattr(regime, "direction", 0) > 0
            else Side.SELL
            if getattr(regime, "direction", 0) < 0
            else None
        )
        if trigger is not None:
            if state is OpportunityState.NONE:
                continue
            elif state is OpportunityState.SETUP:
                lifecycle.append(
                    (
                        OpportunityStateEvent.ARMED,
                        closed_at,
                        closed_at,
                        "V1 retest conditions are closed",
                        trigger.side,
                    )
                )
                state = OpportunityState.ARMED
            lifecycle.append(
                (
                    OpportunityStateEvent.TRIGGERED,
                    closed_at,
                    closed_at,
                    trigger.reason,
                    trigger.side,
                )
            )
            state = OpportunityState.TRIGGERED
            active_index = index
        elif phase is not None and state in (
            OpportunityState.NONE,
            OpportunityState.SETUP,
            OpportunityState.ARMED,
        ):
            if state is OpportunityState.NONE:
                lifecycle.append(
                    (OpportunityStateEvent.SETUP_DETECTED, closed_at, closed_at, phase_reason, side)
                )
                state = OpportunityState.SETUP
            if phase is OpportunityStateEvent.ARMED and state is OpportunityState.SETUP:
                lifecycle.append(
                    (OpportunityStateEvent.ARMED, closed_at, closed_at, phase_reason, side)
                )
                state = OpportunityState.ARMED
            if state is OpportunityState.SETUP:
                active_index = index
        elif (
            state in (OpportunityState.SETUP, OpportunityState.ARMED)
            and getattr(regime, "regime", None) is not MarketRegime.DIRECTIONAL
        ):
            lifecycle.append(
                (
                    OpportunityStateEvent.INVALIDATED,
                    closed_at,
                    closed_at,
                    "directional context was invalidated",
                    side,
                )
            )
            state = OpportunityState.INVALIDATED
            active_index = None
        elif (
            active_index is not None
            and state in (OpportunityState.SETUP, OpportunityState.ARMED)
            and (
                mechanism is OpportunityMechanism.BREAK_RETEST_REACCEL
                and index - active_index >= 4
                or mechanism is OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION
            )
        ):
            lifecycle.append(
                (
                    OpportunityStateEvent.EXPIRED,
                    closed_at,
                    closed_at,
                    "native setup window ended without a trigger",
                    side,
                )
            )
            state = OpportunityState.EXPIRED
            active_index = None
        if (
            state
            in (OpportunityState.TRIGGERED, OpportunityState.INVALIDATED, OpportunityState.EXPIRED)
            and index < len(bars_m5) - 1
        ):
            state = OpportunityState.NONE
            lifecycle = []
    if not lifecycle:
        return OpportunityStateSnapshot(
            symbol=symbol,
            mechanism=mechanism,
            state=OpportunityState.NONE,
            updated_at=evaluated_at,
            reason="no current causal setup detected",
        )
    return _snapshot_from_events(symbol, mechanism, evaluated_at, lifecycle)
