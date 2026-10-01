from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.admission import AdmissionState
from app.domain.asset_specialization import (
    ACTIVE_ASSETS,
    AssetMechanismEvidence,
    AssetMechanismRole,
    AssetProfileStatus,
    AssetSpecializationResearchRequest,
    AssetSpecializationResearchResult,
    AssetSpecializationResearchRow,
    AssetSpecializationSnapshot,
    EvidenceAlignment,
)
from app.domain.opportunity import OpportunityMechanism, PortfolioResearchRequest
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.paper_registry import load_paper_registry
from app.services.runtime_admission_registry import load_research_admissions
from app.services.shadow_overview import load_shadow_overview

_PRIMARY: dict[str, tuple[OpportunityMechanism, ...]] = {
    "BTCUSD": (
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.POST_SHOCK_CONTINUATION,
        OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    ),
    "EURUSD": (
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
    ),
    "GBPUSD": (
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    ),
    "XAUUSD": (
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.POST_SHOCK_CONTINUATION,
        OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
    ),
    "XAGUSD": (),
}
_SECONDARY: dict[str, tuple[OpportunityMechanism, ...]] = {
    "BTCUSD": (OpportunityMechanism.FAILED_AUCTION_REVERSAL,),
    "EURUSD": (OpportunityMechanism.FAILED_AUCTION_REVERSAL, OpportunityMechanism.POST_SHOCK_CONTINUATION),
    "GBPUSD": (OpportunityMechanism.FAILED_AUCTION_REVERSAL, OpportunityMechanism.POST_SHOCK_CONTINUATION),
    "XAUUSD": (OpportunityMechanism.DIRECTIONAL_TRANSITION,),
    "XAGUSD": (
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        OpportunityMechanism.POST_SHOCK_CONTINUATION,
    ),
}
_INCOMPATIBLE = {
    ("EURUSD", OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE),
    ("GBPUSD", OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE),
    ("XAGUSD", OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE),
    ("BTCUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE),
    ("EURUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE),
    ("GBPUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE),
    ("XAGUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE),
}


def _role(symbol: str, mechanism: OpportunityMechanism) -> AssetMechanismRole:
    if mechanism in _PRIMARY[symbol]:
        return AssetMechanismRole.PRIMARY_HYPOTHESIS
    if mechanism in _SECONDARY[symbol]:
        return AssetMechanismRole.SECONDARY_HYPOTHESIS
    return AssetMechanismRole.GENERIC_BASELINE


def _alignment(historical: AdmissionState | None, prospective: str | None, paper_present: bool, paper_n: int) -> EvidenceAlignment:
    if historical is None and not paper_present:
        return EvidenceAlignment.NO_EVIDENCE
    if historical is not None and not paper_present:
        return EvidenceAlignment.HISTORICAL_ONLY
    if historical == AdmissionState.REJECTED and prospective == "supports_demo":
        return EvidenceAlignment.CONFLICTED
    if historical == AdmissionState.ACTIVE and prospective == "failed":
        return EvidenceAlignment.CONFLICTED
    if historical is None:
        return EvidenceAlignment.PROSPECTIVE_COLLECTING if prospective == "collecting" else EvidenceAlignment.PROSPECTIVE_ONLY
    return EvidenceAlignment.HISTORICAL_AND_PROSPECTIVE


def build_asset_specialization_snapshots(runtime_dir: Path, now: datetime) -> list[AssetSpecializationSnapshot]:
    admissions = load_research_admissions(runtime_dir / "strategy_admissions.json")
    paper = {row.strategy_id: row for row in load_paper_registry(runtime_dir, now, settings.paper_evidence_cutover_at)}
    shadow = {f"{row.symbol}:{row.mechanism.value}": row for row in load_shadow_overview(runtime_dir, symbols=ACTIVE_ASSETS)}
    result: list[AssetSpecializationSnapshot] = []
    for symbol in ACTIVE_ASSETS:
        rows: list[AssetMechanismEvidence] = []
        for mechanism in OpportunityMechanism:
            strategy_id = f"{symbol}:{mechanism.value}"
            admission = admissions.get(strategy_id)
            paper_row = paper.get(strategy_id)
            shadow_row = shadow.get(strategy_id)
            compatible = (symbol, mechanism) not in _INCOMPATIBLE
            rows.append(AssetMechanismEvidence(
                mechanism=mechanism, role=_role(symbol, mechanism), compatible=compatible,
                compatibility_reason=None if compatible else "mechanism is not compatible with this asset playbook",
                strategy_id=strategy_id, historical_state=admission.state if admission else None,
                weakest_historical_expectancy_r=admission.weakest_expectancy_r if admission else None,
                historical_worst_drawdown_r=admission.worst_drawdown_r if admission else None,
                historical_paper_collection_candidate=admission.paper_collection_candidate if admission else None,
                prospective_state=paper_row.qualification.state.value if paper_row else None,
                paper_n=paper_row.summary.closed_trades if paper_row else 0,
                paper_expectancy_r=paper_row.summary.expectancy_r if paper_row else None,
                paper_profit_factor=paper_row.summary.profit_factor if paper_row else None,
                paper_max_drawdown_r=paper_row.summary.max_drawdown_r if paper_row else None,
                paper_total_r=paper_row.summary.total_r if paper_row else None,
                paper_pnl_eur=paper_row.summary.total_pnl_eur if paper_row else None,
                open_trade=paper_row.summary.open_trade is not None if paper_row else False,
                shadow_state=shadow_row.state.value if shadow_row else None,
                shadow_side=shadow_row.side.value if shadow_row and shadow_row.side else None,
                shadow_reason=shadow_row.reason if shadow_row else None,
                evidence_alignment=_alignment(admission.state if admission else None, paper_row.qualification.state.value if paper_row else None, paper_row is not None, paper_row.summary.closed_trades if paper_row else 0),
            ))
        result.append(AssetSpecializationSnapshot(symbol=symbol, profile_status=AssetProfileStatus.VIABILITY_RESEARCH if symbol == "XAGUSD" else AssetProfileStatus.STANDARD, primary_mechanisms=list(_PRIMARY[symbol]), secondary_mechanisms=list(_SECONDARY[symbol]), mechanism_evidence=rows, evidence_reason="descriptive playbook hypotheses; generic baseline remains collected"))
    return result


def evaluate_asset_specialization(
    files_dir: Path,
    request: AssetSpecializationResearchRequest,
) -> AssetSpecializationResearchResult:
    symbols = [symbol.upper() for symbol in request.symbols] if request.symbols else list(ACTIVE_ASSETS)
    invalid_symbols = sorted(set(symbols) - set(ACTIVE_ASSETS))
    if invalid_symbols:
        raise ValueError(f"asset specialization supports only {', '.join(ACTIVE_ASSETS)}; invalid symbols: {', '.join(invalid_symbols)}")
    portfolio_request = PortfolioResearchRequest(split=request.split, symbols=symbols)
    raw = run_mt4_portfolio_research(files_dir, portfolio_request, macro_events_path=settings.macro_events_path, research_execution_model_path=settings.research_execution_model_path)
    rows: list[AssetSpecializationResearchRow] = []
    for item in raw.results:
        role = _role(item.symbol, item.mechanism)
        rows.append(AssetSpecializationResearchRow(
            symbol=item.symbol, mechanism=item.mechanism, role=role, candidates=item.candidates,
            executed=item.executed, rejected=item.rejected, rejection_reasons=item.rejection_reasons,
            validation_trades=item.validation.trades, validation_expectancy_r=item.validation.expectancy_r,
            validation_profit_factor=item.validation.profit_factor, validation_max_drawdown_r=item.validation.max_drawdown_r,
            validation_average_execution_cost_r=item.validation.average_execution_cost_r,
            holdout_trades=item.holdout.trades, holdout_expectancy_r=item.holdout.expectancy_r,
            holdout_profit_factor=item.holdout.profit_factor, holdout_max_drawdown_r=item.holdout.max_drawdown_r,
            holdout_average_execution_cost_r=item.holdout.average_execution_cost_r,
            admission_state=item.admission.state,
        ))
    return AssetSpecializationResearchResult(rows=rows, raw_portfolio_result=raw)
