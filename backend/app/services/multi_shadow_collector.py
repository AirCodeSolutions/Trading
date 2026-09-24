from datetime import datetime
from pathlib import Path

from app.core.config import ExecutionMode, settings
from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowCollectionResult
from app.services.admission import paper_entry_allowed
from app.services.blocked_probe import advance_blocked_probe_book
from app.services.market_universe import build_market_universe
from app.services.mt4_market_data import load_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.prospective_qualification import (
    assess_prospective,
    prospective_entry_allowed,
)
from app.services.runtime_admission_registry import load_research_admissions
from app.services.runtime_capital import resolve_demo_sizing_capital
from app.services.shadow_ledger import append_shadow_observation
from app.services.shadow_paper import (
    advance_shadow_paper_book,
    load_shadow_paper_state,
)
from app.services.shadow_scanner import scan_shadow_opportunity

_MECHANISM_SLUG = {
    OpportunityMechanism.BREAK_RETEST_REACCEL: "break_retest",
    OpportunityMechanism.FAILED_AUCTION_REVERSAL: "failed_auction",
    OpportunityMechanism.POST_SHOCK_CONTINUATION: "post_shock",
    OpportunityMechanism.DIRECTIONAL_TRANSITION: "directional_transition",
    OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION: "directional_pullback",
    OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL: "asia_range_sweep",
    OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE: "structural_displacement_sequence",
    OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE: "structural_persistence_sequence",
}


def collect_all_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
    *,
    allow_paper_entries: bool = True,
) -> list[ShadowCollectionResult]:
    results: list[ShadowCollectionResult] = []
    admissions = load_research_admissions(runtime_dir / "strategy_admissions.json")
    runtime_capital = resolve_demo_sizing_capital(files_dir)
    sizing_capital_eur: float | None = None
    if settings.execution_mode == ExecutionMode.DEMO:
        sizing_capital_eur = runtime_capital.capital_eur or 0.0
    assets = [
        asset
        for asset in build_market_universe(
            files_dir,
            evaluated_at,
            symbols=settings.session_watch_symbols,
        )
        if asset.paper_ready and asset.quote_live
    ]

    for asset in assets:
        spec = get_mt4_symbol_spec(files_dir, asset.symbol)
        if spec is None:
            continue
        bars_m5 = load_closed_market_bars(
            files_dir,
            asset.symbol,
            timeframe=Timeframe.M5,
            evaluated_at=evaluated_at,
        )
        bars_m15 = load_closed_market_bars(
            files_dir,
            asset.symbol,
            timeframe=Timeframe.M15,
            evaluated_at=evaluated_at,
        )
        if len(bars_m5) < 30 or len(bars_m15) < 50:
            continue

        for mechanism in OpportunityMechanism:
            if not shadow_mechanism_enabled(asset.symbol, mechanism):
                continue
            diagnostic = scan_shadow_opportunity(
                bars_m5,
                bars_m15,
                spec,
                mechanism,
                evaluated_at,
                capital_eur=sizing_capital_eur,
            )
            slug = _MECHANISM_SLUG[mechanism]
            prefix = f"{asset.symbol}_{slug}"
            ledger_path = runtime_dir / f"{prefix}.jsonl"
            appended = append_shadow_observation(ledger_path, diagnostic)
            strategy_id = f"{asset.symbol}:{mechanism.value}"
            admission = admissions.get(strategy_id)
            state_path = runtime_dir / f"{prefix}_paper_state.json"
            allow_new_entries = (
                allow_paper_entries
                and paper_entry_allowed(admission)
                and not symbol_has_open_paper_elsewhere(
                    runtime_dir,
                    asset.symbol,
                    current_state_path=state_path,
                )
            )
            paper = advance_shadow_paper_book(
                diagnostic=diagnostic,
                spec=spec,
                bars_m5=bars_m5,
                state_path=state_path,
                trades_path=runtime_dir / f"{prefix}_paper_trades.jsonl",
                evaluated_at=evaluated_at,
                allow_new_entries=allow_new_entries,
                evidence_cutover_at=settings.paper_evidence_cutover_at,
                prospective_entry_guard=lambda summary, strategy_id=strategy_id: (
                    prospective_entry_allowed(
                        assess_prospective(strategy_id, summary)
                    )
                ),
            )
            unqualified_state_path = (
                runtime_dir / f"{prefix}_unqualified_probe_state.json"
            )
            unqualified_allowed = unqualified_probe_entry_allowed(admission)
            if should_advance_unqualified_probe(admission, unqualified_state_path):
                advance_shadow_paper_book(
                    diagnostic=diagnostic,
                    spec=spec,
                    bars_m5=bars_m5,
                    state_path=unqualified_state_path,
                    trades_path=runtime_dir / f"{prefix}_unqualified_probes.jsonl",
                    evaluated_at=evaluated_at,
                    allow_new_entries=unqualified_allowed,
                )
            advance_blocked_probe_book(
                diagnostic=diagnostic,
                spec=spec,
                bars_m5=bars_m5,
                state_path=runtime_dir / f"{prefix}_blocked_probe_state.json",
                probes_path=runtime_dir / f"{prefix}_blocked_probes.jsonl",
                evaluated_at=evaluated_at,
            )
            results.append(
                ShadowCollectionResult(
                    appended=appended,
                    ledger_path=str(ledger_path),
                    diagnostic=diagnostic,
                    paper=paper,
                )
            )

    return results


def symbol_has_open_paper_elsewhere(
    runtime_dir: Path,
    symbol: str,
    *,
    current_state_path: Path,
) -> bool:
    pattern = f"{symbol.upper()}_*_paper_state.json"
    current = current_state_path.resolve()
    for state_path in runtime_dir.glob(pattern):
        if state_path.resolve() == current:
            continue
        if load_shadow_paper_state(state_path).open_trade is not None:
            return True
    return False


def should_advance_unqualified_probe(admission, state_path: Path) -> bool:
    return unqualified_probe_entry_allowed(admission) or state_path.is_file()


def unqualified_probe_entry_allowed(admission) -> bool:
    return not paper_entry_allowed(admission)


def shadow_mechanism_enabled(
    symbol: str,
    mechanism: OpportunityMechanism,
) -> bool:
    if mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE:
        return symbol.upper() in {"BTCUSD", "XAUUSD"}
    if mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE:
        return symbol.upper() == "XAUUSD"
    if mechanism == OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
        return symbol.upper() == "GBPUSD"
    if mechanism == OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL:
        return symbol.upper() in {"GBPUSD", "XAUUSD"}
    return True
