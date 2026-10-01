from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.admission import AdmissionState
from app.domain.champion_challengers import (
    ChallengerEvidenceState,
    ChampionChallengerReport,
)
from app.domain.demo_execution import DemoExecutionStatus
from app.domain.economic_validation_v2 import (
    EconomicEvidenceState,
    EconomicValidationReport,
    FamilyEconomicValidation,
    OperationalDeploymentGate,
    TradeEconomics,
)
from app.domain.execution_audit import ExecutionQualitySummary
from app.domain.opportunity_funnel import OpportunityFunnel
from app.domain.portfolio import (
    PaperStrategyRuntime,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.domain.portfolio_allocator import PortfolioOpportunityAllocationReport
from app.domain.position_manager import PositionManagerReport
from app.domain.shadow_paper import ShadowPaperTrade
from app.services.prospective_qualification import MIN_PROSPECTIVE_TRADES


def summarize_trade_economics(
    trades: Sequence[ShadowPaperTrade],
) -> TradeEconomics:
    resolved = sorted(
        (trade for trade in trades if trade.result_r is not None),
        key=lambda trade: (trade.opened_at, trade.trade_id),
    )
    values = [float(trade.result_r) for trade in resolved if trade.result_r is not None]
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return TradeEconomics(
        trades=len(values),
        wins=sum(value > 0 for value in values),
        losses=sum(value < 0 for value in values),
        total_r=sum(values),
        expectancy_r=sum(values) / len(values) if values else None,
        profit_factor=(
            gains / losses
            if losses > 0
            else 99.0
            if gains > 0
            else None
        ),
        win_rate=sum(value > 0 for value in values) / len(values) if values else None,
        max_drawdown_r=drawdown,
        total_pnl_eur=sum(trade.pnl_eur or 0.0 for trade in resolved),
    )


def _family_state(
    row: PaperStrategyRuntime | None,
) -> EconomicEvidenceState:
    if row is None or row.qualification.closed_trades == 0:
        return EconomicEvidenceState.NO_EVIDENCE
    if row.qualification.state == ProspectiveQualificationState.FAILED:
        return EconomicEvidenceState.NEGATIVE
    if (
        row.qualification.state == ProspectiveQualificationState.SUPPORTS_DEMO
        and row.historical_state == AdmissionState.ACTIVE
    ):
        return EconomicEvidenceState.SUPPORTS_DEMO_EVALUATION
    return EconomicEvidenceState.COLLECTING


def _average(values: Sequence[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def _deployment_gate(
    overview: TradingOverview,
    demo: DemoExecutionStatus,
    *,
    drain_enabled: bool,
) -> OperationalDeploymentGate:
    paper_open = overview.risk.research_paper_open_positions
    bridge_open = len(demo.bridge_positions)
    pending_open = demo.pending_command is not None
    pending_close = demo.pending_close_command is not None
    book_flat = (
        paper_open == 0
        and bridge_open == 0
        and not pending_open
        and not pending_close
    )
    ready = drain_enabled and book_flat
    reasons: list[str] = []
    if not drain_enabled:
        reasons.append("drain must be ON before deployment")
    if not book_flat:
        reasons.append("Trading-New book is not flat")
    reason = (
        "drain ON and Trading-New book flat"
        if ready
        else "; ".join(reasons)
    )
    return OperationalDeploymentGate(
        drain_enabled=drain_enabled,
        paper_open_positions=paper_open,
        bridge_open_positions=bridge_open,
        pending_open_command=pending_open,
        pending_close_command=pending_close,
        book_flat=book_flat,
        research_stack_deploy_ready=ready,
        reason=reason,
    )


def _v2_authority_evidence(
    champions: ChampionChallengerReport,
) -> tuple[bool, list[str]]:
    required = {"TRIGGER_V2", "ENTRY_ZONE_V2", "POSITION_MANAGER_V2"}
    for family in champions.families:
        reviewable = {
            challenger.variant_id
            for challenger in family.challengers
            if challenger.evidence_state == ChallengerEvidenceState.REVIEWABLE
        }
        if required <= reviewable:
            return True, []
    gaps: list[str] = []
    for variant in sorted(required):
        if not any(
            challenger.variant_id == variant
            and challenger.evidence_state == ChallengerEvidenceState.REVIEWABLE
            for family in champions.families
            for challenger in family.challengers
        ):
            gaps.append(f"{variant} has no reviewable paired-outcome evidence")
    return False, gaps


def build_economic_validation_report(
    *,
    now: datetime,
    window_hours: int,
    trades: Sequence[ShadowPaperTrade],
    overview: TradingOverview,
    funnel: OpportunityFunnel,
    position_manager: PositionManagerReport,
    champions: ChampionChallengerReport,
    execution_quality: ExecutionQualitySummary,
    allocator: PortfolioOpportunityAllocationReport,
    demo: DemoExecutionStatus,
    drain_enabled: bool,
    broker_realized_pnl_eur_today: float | None,
    broker_closed_trades_window: int,
    broker_realized_pnl_eur_window: float | None,
    broker_missing_tickets_window: list[int],
    broker_history_complete: bool,
) -> EconomicValidationReport:
    family_trades: dict[str, list[ShadowPaperTrade]] = {}
    for trade in trades:
        key = f"{trade.symbol}:{trade.mechanism.value}"
        family_trades.setdefault(key, []).append(trade)
    paper_rows = {row.strategy_id: row for row in overview.paper_strategies}
    funnel_rows = {row.strategy_id: row for row in funnel.strategies}
    pm_rows: dict[str, list] = {}
    for comparison in position_manager.comparisons:
        if comparison.pending or comparison.invalid_data:
            continue
        key = f"{comparison.symbol}:{comparison.mechanism.value}"
        pm_rows.setdefault(key, []).append(comparison)

    families: list[FamilyEconomicValidation] = []
    for family in champions.families:
        key = family.family_id
        row = paper_rows.get(key)
        funnel_row = funnel_rows.get(key)
        comparisons = pm_rows.get(key, [])
        pm_baseline = [
            item.baseline_result_r
            for item in comparisons
            if item.baseline_result_r is not None
        ]
        pm_v2 = [
            item.v2_result_r
            for item in comparisons
            if item.v2_result_r is not None
        ]
        reviewable = [
            challenger.variant_id
            for challenger in family.challengers
            if challenger.evidence_state == ChallengerEvidenceState.REVIEWABLE
        ]
        gaps = list(family.evidence_gaps)
        if row is None or row.qualification.closed_trades < MIN_PROSPECTIVE_TRADES:
            gaps.append(
                "prospective family evidence below "
                f"{MIN_PROSPECTIVE_TRADES} closed trades"
            )
        families.append(
            FamilyEconomicValidation(
                strategy_id=key,
                symbol=family.symbol,
                mechanism=family.mechanism,
                asset_role=family.asset_role.value,
                evidence_state=_family_state(row),
                historical_state=(
                    row.historical_state.value
                    if row and row.historical_state
                    else None
                ),
                prospective_state=(
                    row.qualification.state.value if row else None
                ),
                paper=summarize_trade_economics(family_trades.get(key, [])),
                signal_rows=funnel_row.signal_rows if funnel_row else 0,
                executable_signal_rows=(
                    funnel_row.executable_signal_rows if funnel_row else 0
                ),
                blocked_signal_rows=(
                    funnel_row.blocked_signal_rows if funnel_row else 0
                ),
                unqualified_probe_trades=(
                    funnel_row.resolved_unqualified_probes if funnel_row else 0
                ),
                unqualified_probe_total_r=(
                    funnel_row.unqualified_probe_total_r if funnel_row else 0.0
                ),
                blocked_probe_trades=(
                    funnel_row.resolved_blocked_probes if funnel_row else 0
                ),
                blocked_probe_total_r=(
                    funnel_row.blocked_total_r if funnel_row else 0.0
                ),
                pm_paired_trades=min(len(pm_baseline), len(pm_v2)),
                pm_baseline_total_r=sum(pm_baseline) if pm_baseline else None,
                pm_v2_total_r=sum(pm_v2) if pm_v2 else None,
                pm_delta_r=(
                    sum(pm_v2) - sum(pm_baseline)
                    if pm_baseline and len(pm_baseline) == len(pm_v2)
                    else None
                ),
                pm_baseline_mfe_r=_average(
                    [item.baseline_mfe_r for item in comparisons]
                ),
                pm_v2_mfe_r=_average(
                    [item.v2_mfe_r for item in comparisons]
                ),
                pm_baseline_mae_r=_average(
                    [item.baseline_mae_r for item in comparisons]
                ),
                pm_v2_mae_r=_average(
                    [item.v2_mae_r for item in comparisons]
                ),
                pm_baseline_mfe_capture=_average(
                    [item.baseline_mfe_capture for item in comparisons]
                ),
                pm_v2_mfe_capture=_average(
                    [item.v2_mfe_capture for item in comparisons]
                ),
                pm_baseline_giveback_r=_average(
                    [item.baseline_giveback_r for item in comparisons]
                ),
                pm_v2_giveback_r=_average(
                    [item.v2_giveback_r for item in comparisons]
                ),
                reviewable_challengers=reviewable,
                evidence_gaps=sorted(set(gaps)),
            )
        )

    supporting = sum(
        family.evidence_state == EconomicEvidenceState.SUPPORTS_DEMO_EVALUATION
        for family in families
    )
    failed = sum(
        family.evidence_state == EconomicEvidenceState.NEGATIVE
        for family in families
    )
    collecting = sum(
        family.evidence_state == EconomicEvidenceState.COLLECTING
        for family in families
    )
    paper = summarize_trade_economics(trades)
    if supporting:
        economic_state = EconomicEvidenceState.SUPPORTS_DEMO_EVALUATION
    elif failed:
        economic_state = EconomicEvidenceState.NEGATIVE
    elif paper.trades:
        economic_state = EconomicEvidenceState.COLLECTING
    else:
        economic_state = EconomicEvidenceState.NO_EVIDENCE

    v2_supported, v2_gaps = _v2_authority_evidence(champions)
    deployment = _deployment_gate(
        overview,
        demo,
        drain_enabled=drain_enabled,
    )
    return EconomicValidationReport(
        generated_at=now,
        window_hours=window_hours,
        window_start=now - timedelta(hours=window_hours),
        window_end=now,
        capital_eur=overview.risk.reference_capital_eur,
        capital_source=overview.risk.reference_capital_source,
        paper=paper,
        paper_open_positions=overview.risk.research_paper_open_positions,
        paper_open_risk_eur=overview.risk.research_paper_open_risk_eur,
        bridge_open_positions=len(demo.bridge_positions),
        bridge_unrealized_pnl_eur=sum(item.profit for item in demo.bridge_positions),
        broker_realized_pnl_eur_today=broker_realized_pnl_eur_today,
        broker_closed_trades_window=broker_closed_trades_window,
        broker_realized_pnl_eur_window=broker_realized_pnl_eur_window,
        broker_missing_tickets_window=broker_missing_tickets_window,
        broker_history_complete=broker_history_complete,
        signal_rows=funnel.signal_rows,
        executable_signal_rows=funnel.executable_signal_rows,
        blocked_signal_rows=funnel.blocked_signal_rows,
        block_reasons=funnel.block_reasons,
        unqualified_probe_trades=funnel.resolved_unqualified_probes,
        unqualified_probe_total_r=funnel.unqualified_probe_total_r,
        blocked_probe_trades=funnel.resolved_blocked_probes,
        blocked_probe_total_r=funnel.blocked_total_r,
        pm_paired_trades=position_manager.trades,
        pm_baseline_total_r=position_manager.baseline_total_r,
        pm_v2_total_r=position_manager.v2_total_r,
        pm_delta_r=position_manager.delta_r,
        execution_quality=execution_quality,
        families_supporting_demo=supporting,
        families_failed=failed,
        families_collecting=collecting,
        economic_state=economic_state,
        v2_authority_cutover_supported=v2_supported,
        v2_authority_gaps=v2_gaps,
        allocator_ready=allocator.ready,
        allocator_selected_strategy_ids=allocator.selected_strategy_ids,
        deployment=deployment,
        families=families,
        limitations=[
            "No profitability guarantee: evidence is descriptive and prospective.",
            "Trigger V2 and Entry Zone V2 require paired outcome evidence before authority cutover.",
            "Research-stack deployment and V2 broker-authority cutover are separate gates.",
        ],
    )
