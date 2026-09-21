from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowCollectionResult
from app.services.blocked_probe import advance_blocked_probe_book
from app.services.market_universe import build_market_universe
from app.services.mt4_market_data import load_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.runtime_admission_registry import load_research_admissions
from app.services.shadow_ledger import append_shadow_observation
from app.services.shadow_paper import advance_shadow_paper_book
from app.services.shadow_scanner import scan_shadow_opportunity

_MECHANISM_SLUG = {
    OpportunityMechanism.BREAK_RETEST_REACCEL: "break_retest",
    OpportunityMechanism.FAILED_AUCTION_REVERSAL: "failed_auction",
    OpportunityMechanism.POST_SHOCK_CONTINUATION: "post_shock",
    OpportunityMechanism.DIRECTIONAL_TRANSITION: "directional_transition",
}


def collect_all_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
) -> list[ShadowCollectionResult]:
    results: list[ShadowCollectionResult] = []
    admissions = load_research_admissions(runtime_dir / "strategy_admissions.json")
    assets = [
        asset
        for asset in build_market_universe(files_dir, evaluated_at)
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
            diagnostic = scan_shadow_opportunity(
                bars_m5,
                bars_m15,
                spec,
                mechanism,
                evaluated_at,
            )
            slug = _MECHANISM_SLUG[mechanism]
            prefix = f"{asset.symbol}_{slug}"
            ledger_path = runtime_dir / f"{prefix}.jsonl"
            appended = append_shadow_observation(ledger_path, diagnostic)
            strategy_id = f"{asset.symbol}:{mechanism.value}"
            admission = admissions.get(strategy_id)
            allow_new_entries = paper_entry_allowed(admission)
            paper = advance_shadow_paper_book(
                diagnostic=diagnostic,
                spec=spec,
                bars_m5=bars_m5,
                state_path=runtime_dir / f"{prefix}_paper_state.json",
                trades_path=runtime_dir / f"{prefix}_paper_trades.jsonl",
                evaluated_at=evaluated_at,
                allow_new_entries=allow_new_entries,
                evidence_cutover_at=settings.paper_evidence_cutover_at,
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



def paper_entry_allowed(
    admission: AdmissionDecision | None,
) -> bool:
    return (
        admission is not None
        and admission.state != AdmissionState.REJECTED
    )
