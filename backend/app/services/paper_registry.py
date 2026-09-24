from datetime import datetime
from pathlib import Path

from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import PaperStrategyRuntime
from app.services.prospective_qualification import assess_prospective
from app.services.shadow_paper import load_closed_trades, load_shadow_paper_summary

_SLUG_TO_MECHANISM = {
    "break_retest": OpportunityMechanism.BREAK_RETEST_REACCEL,
    "failed_auction": OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    "post_shock": OpportunityMechanism.POST_SHOCK_CONTINUATION,
    "directional_transition": OpportunityMechanism.DIRECTIONAL_TRANSITION,
    "directional_pullback": OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
    "asia_range_sweep": OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    "structural_displacement_sequence": OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    "structural_persistence_sequence": OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
}


def load_paper_registry(
    runtime_dir: Path,
    now: datetime | None = None,
    evidence_cutover_at: datetime | None = None,
) -> list[PaperStrategyRuntime]:
    rows: list[PaperStrategyRuntime] = []
    for state_path in sorted(runtime_dir.glob("*_paper_state.json")):
        parsed = _parse_state_name(state_path)
        if parsed is None:
            continue
        symbol, mechanism, prefix = parsed
        trades_path = runtime_dir / f"{prefix}_paper_trades.jsonl"
        summary = load_shadow_paper_summary(
            state_path,
            trades_path,
            evidence_cutover_at=evidence_cutover_at,
        )
        strategy_id = f"{symbol}:{mechanism.value}"
        qualification = assess_prospective(strategy_id, summary)
        daily_pnl, daily_r = _daily_results(
            trades_path,
            now,
            evidence_cutover_at,
        )
        rows.append(
            PaperStrategyRuntime(
                strategy_id=strategy_id,
                symbol=symbol,
                mechanism=mechanism,
                summary=summary,
                qualification=qualification,
                daily_pnl_eur=daily_pnl,
                daily_r=daily_r,
            )
        )
    return rows


def _daily_results(
    trades_path: Path,
    now: datetime | None,
    evidence_cutover_at: datetime | None,
) -> tuple[float, float]:
    if now is None:
        return 0.0, 0.0
    trades = load_closed_trades(trades_path)
    daily = [
        trade
        for trade in trades
        if trade.exit_at is not None
        and trade.exit_at.date() == now.date()
        and (
            evidence_cutover_at is None
            or trade.opened_at >= evidence_cutover_at
        )
    ]
    return (
        sum(trade.pnl_eur or 0.0 for trade in daily),
        sum(trade.result_r or 0.0 for trade in daily),
    )


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
