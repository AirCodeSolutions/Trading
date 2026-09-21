from pathlib import Path

from app.domain.blocked_probe import BlockedProbeRuntime
from app.domain.opportunity import OpportunityMechanism
from app.services.blocked_probe import load_blocked_probe_summary

_SLUG_TO_MECHANISM = {
    "break_retest": OpportunityMechanism.BREAK_RETEST_REACCEL,
    "failed_auction": OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    "post_shock": OpportunityMechanism.POST_SHOCK_CONTINUATION,
    "directional_transition": OpportunityMechanism.DIRECTIONAL_TRANSITION,
}


def load_blocked_probe_registry(
    runtime_dir: Path,
) -> list[BlockedProbeRuntime]:
    rows: list[BlockedProbeRuntime] = []
    for state_path in sorted(runtime_dir.glob("*_blocked_probe_state.json")):
        parsed = _parse_state_name(state_path)
        if parsed is None:
            continue
        symbol, mechanism, prefix = parsed
        summary = load_blocked_probe_summary(
            state_path,
            runtime_dir / f"{prefix}_blocked_probes.jsonl",
        )
        rows.append(
            BlockedProbeRuntime(
                strategy_id=f"{symbol}:{mechanism.value}",
                symbol=symbol,
                mechanism=mechanism,
                summary=summary,
            )
        )
    return rows


def _parse_state_name(
    path: Path,
) -> tuple[str, OpportunityMechanism, str] | None:
    stem = path.name.removesuffix("_blocked_probe_state.json")
    for slug, mechanism in _SLUG_TO_MECHANISM.items():
        suffix = f"_{slug}"
        if stem.endswith(suffix):
            symbol = stem.removesuffix(suffix)
            if symbol:
                return symbol, mechanism, stem
    return None
