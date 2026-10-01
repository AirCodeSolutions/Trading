from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


def resolve_trigger_structural_stop(
    mechanism: OpportunityMechanism,
    side: Side,
    raw_stop: float,
    entry: float,
    stop_atr: float,
    spread: float,
) -> float:
    """Resolve the existing shadow stop geometry without changing its rules."""
    if mechanism in {
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    }:
        return raw_stop if side is Side.BUY else raw_stop + spread
    if mechanism is OpportunityMechanism.BREAK_RETEST_REACCEL:
        if side is Side.BUY:
            return min(raw_stop, entry - stop_atr)
        return max(raw_stop + spread, entry + stop_atr)
    raise ValueError(f"stop geometry unsupported for {mechanism}")
