from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowOpportunityDiagnostic
from app.services.shadow_ledger import load_latest_shadow_observation

_MECHANISM_SLUGS = {
    "break_retest": OpportunityMechanism.BREAK_RETEST_REACCEL,
    "failed_auction": OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    "post_shock": OpportunityMechanism.POST_SHOCK_CONTINUATION,
    "directional_transition": OpportunityMechanism.DIRECTIONAL_TRANSITION,
    "directional_pullback": OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
    "asia_range_sweep": OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    "structural_displacement_sequence": OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    "structural_persistence_sequence": OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
}


def load_shadow_overview(
    runtime_dir: Path,
    *,
    symbols: tuple[str, ...] | None = None,
) -> list[ShadowOpportunityDiagnostic]:
    allowed = {symbol.upper() for symbol in symbols} if symbols else None
    rows: list[ShadowOpportunityDiagnostic] = []

    for slug in _MECHANISM_SLUGS:
        for path in runtime_dir.glob(f"*_{slug}.jsonl"):
            symbol = path.stem.removesuffix(f"_{slug}").upper()
            if not symbol or (allowed is not None and symbol not in allowed):
                continue
            diagnostic = load_latest_shadow_observation(path)
            if diagnostic is None:
                continue
            if diagnostic.symbol.upper() != symbol:
                continue
            rows.append(diagnostic)

    rows.sort(key=lambda row: (row.symbol, row.mechanism.value))
    return rows
