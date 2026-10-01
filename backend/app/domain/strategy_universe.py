from app.domain.opportunity import OpportunityMechanism

ACTIVE_ASSETS = ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD")

MECHANISM_SLUGS: dict[str, OpportunityMechanism] = {
    "break_retest": OpportunityMechanism.BREAK_RETEST_REACCEL,
    "failed_auction": OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    "post_shock": OpportunityMechanism.POST_SHOCK_CONTINUATION,
    "directional_transition": OpportunityMechanism.DIRECTIONAL_TRANSITION,
    "directional_pullback": OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
    "asia_range_sweep": OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    "structural_displacement_sequence": OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    "structural_persistence_sequence": OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
}


def mechanism_is_compatible(
    symbol: str,
    mechanism: OpportunityMechanism,
) -> bool:
    normalized = symbol.upper()
    if normalized not in ACTIVE_ASSETS:
        return False
    if mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE:
        return normalized in {"BTCUSD", "XAUUSD"}
    if mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE:
        return normalized == "XAUUSD"
    return True


INCOMPATIBLE_FAMILIES = frozenset(
    (symbol, mechanism)
    for symbol in ACTIVE_ASSETS
    for mechanism in OpportunityMechanism
    if not mechanism_is_compatible(symbol, mechanism)
)


def compatible_mechanisms(symbol: str) -> tuple[OpportunityMechanism, ...]:
    return tuple(
        mechanism
        for mechanism in OpportunityMechanism
        if mechanism_is_compatible(symbol, mechanism)
    )


def strategy_id(symbol: str, mechanism: OpportunityMechanism) -> str:
    return f"{symbol.upper()}:{mechanism.value}"
