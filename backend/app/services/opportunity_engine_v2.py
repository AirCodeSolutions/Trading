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
from app.services.opportunity_strategies import generate_candidates

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
    source_bar_at: datetime,
    reason: str,
) -> tuple[OpportunityState, OpportunityStateTransition]:
    target = {
        OpportunityStateEvent.SETUP_DETECTED: OpportunityState.SETUP,
        OpportunityState.ARMED: OpportunityState.ARMED,
        OpportunityState.TRIGGERED: OpportunityState.TRIGGERED,
        OpportunityState.INVALIDATED: OpportunityState.INVALIDATED,
        OpportunityState.EXPIRED: OpportunityState.EXPIRED,
    }[event]
    if at < source_bar_at:
        raise ValueError("decision cannot precede its source bar")
    if target not in _ALLOWED.get(current, set()):
        raise ValueError(f"invalid opportunity transition: {current} -> {target}")
    return target, OpportunityStateTransition(
        state=target,
        at=at,
        source_bar_at=source_bar_at,
        event=event,
        reason=reason,
    )


def build_opportunity_state(
    *,
    symbol: str,
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    mechanism: OpportunityMechanism,
    evaluated_at: datetime,
) -> OpportunityStateSnapshot:
    if not bars_m5 or not bars_m15:
        return OpportunityStateSnapshot(
            symbol=symbol,
            mechanism=mechanism,
            state=OpportunityState.NONE,
            updated_at=evaluated_at,
            reason="insufficient closed market history",
        )

    latest_bar = bars_m5[-1]
    decision_at = latest_bar.timestamp + timedelta(minutes=5)
    candidates = generate_candidates(bars_m5, bars_m15, mechanism)
    latest_candidate = next(
        (
            candidate
            for candidate in reversed(candidates)
            if candidate.signal_at == decision_at
        ),
        None,
    )
    recent_candidate = next(
        (
            candidate
            for candidate in reversed(candidates)
            if decision_at - timedelta(minutes=15)
            <= candidate.signal_at
            < decision_at
        ),
        None,
    )

    if latest_candidate is not None:
        state = OpportunityState.TRIGGERED
        side = latest_candidate.side
        reason = latest_candidate.reason
        event = OpportunityStateEvent.TRIGGERED
        first_seen_at = latest_candidate.signal_at
        source_bar_at = latest_bar.timestamp
        triggered_at = decision_at
    elif recent_candidate is not None:
        state = OpportunityState.ARMED
        side = recent_candidate.side
        reason = "existing causal setup is armed while trigger is not current"
        event = OpportunityStateEvent.ARMED
        first_seen_at = recent_candidate.signal_at
        source_bar_at = latest_bar.timestamp
        triggered_at = None
    else:
        state = OpportunityState.SETUP if candidates else OpportunityState.NONE
        side = candidates[-1].side if candidates else None
        reason = (
            "causal mechanism context present; trigger not confirmed"
            if candidates
            else "no representative setup detected on closed bars"
        )
        event = (
            OpportunityStateEvent.SETUP_DETECTED
            if candidates
            else None
        )
        first_seen_at = candidates[-1].signal_at if candidates else None
        source_bar_at = latest_bar.timestamp
        triggered_at = None

    provenance: list[OpportunityStateTransition] = []
    if event is not None:
        transition_state, transition = transition_opportunity_state(
            OpportunityState.NONE,
            event=OpportunityStateEvent.SETUP_DETECTED,
            at=decision_at,
            source_bar_at=source_bar_at,
            reason=reason,
        )
        if state == OpportunityState.SETUP:
            provenance.append(transition)
        else:
            armed_state, armed = transition_opportunity_state(
                transition_state,
                event=OpportunityStateEvent.ARMED,
                at=decision_at,
                source_bar_at=source_bar_at,
                reason=reason,
            )
            if state == OpportunityState.ARMED:
                provenance.extend((transition, armed))
            else:
                triggered_state, triggered = transition_opportunity_state(
                    armed_state,
                    event=OpportunityStateEvent.TRIGGERED,
                    at=decision_at,
                    source_bar_at=source_bar_at,
                    reason=reason,
                )
                assert triggered_state == state
                provenance.extend((transition, armed, triggered))

    return OpportunityStateSnapshot(
        symbol=symbol,
        mechanism=mechanism,
        side=side,
        state=state,
        first_seen_at=first_seen_at,
        updated_at=decision_at,
        triggered_at=triggered_at,
        reason=reason,
        provenance=provenance,
    )
