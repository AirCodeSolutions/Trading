from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import PaperStrategyRuntime
from app.services.prospective_qualification import assess_prospective
from app.services.shadow_paper import load_shadow_paper_summary


_SLUG_TO_MECHANISM = {
    "break_retest": OpportunityMechanism.BREAK_RETEST_REACCEL,
    "failed_auction": OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    "post_shock": OpportunityMechanism.POST_SHOCK_CONTINUATION,
}


def load_paper_registry(runtime_dir: Path) -> list[PaperStrategyRuntime]:
    rows: list[PaperStrategyRuntime] = []
    for state_path in sorted(runtime_dir.glob("*_paper_state.json")):
        parsed = _parse_state_name(state_path)
        if parsed is None:
            continue
        symbol, mechanism, prefix = parsed
        trades_path = runtime_dir / f"{prefix}_paper_trades.jsonl"
        summary = load_shadow_paper_summary(state_path, trades_path)
        strategy_id = f"{symbol}:{mechanism.value}"
        qualification = assess_prospective(strategy_id, summary)
        rows.append(
            PaperStrategyRuntime(
                strategy_id=strategy_id,
                symbol=symbol,
                mechanism=mechanism,
                summary=summary,
                qualification=qualification,
            )
        )
    return rows


def _parse_state_name(
    path: Path,
) -> tuple[str, OpportunityMechanism, str] | None:
    stem = path.name.removesuffix("_paper_state.json")
    for slug, mechanism in _SLUG_TO_MECHANISM.items():
        suffix = f"_{slug}"
        if stem.endswith(suffix):
            symbol = stem.removesuffix(suffix)
            if symbol:
                return symbol, mechanism, stem
    return None
