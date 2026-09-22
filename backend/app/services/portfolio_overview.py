from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.admission import AdmissionState
from app.domain.portfolio import (
    PaperStrategyRuntime,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.services.admission import demo_collection_allowed, paper_entry_allowed
from app.services.broker_account import read_broker_demo_snapshot
from app.services.paper_registry import load_paper_registry
from app.services.runtime_admission_registry import load_research_admissions


def build_trading_overview(
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
) -> TradingOverview:
    paper_rows = load_paper_registry(
        runtime_dir,
        now,
        settings.paper_evidence_cutover_at,
    )
    admissions = load_research_admissions(runtime_dir / "strategy_admissions.json")
    paper_rows = [
        row.model_copy(
            update={
                "historical_state": admissions[row.strategy_id].state,
                "historical_weakest_expectancy_r": admissions[
                    row.strategy_id
                ].weakest_expectancy_r,
                "paper_collection_candidate": admissions[
                    row.strategy_id
                ].paper_collection_candidate,
                "paper_entry_allowed": paper_entry_allowed(
                    admissions[row.strategy_id]
                ),
            }
        )
        if row.strategy_id in admissions
        else row
        for row in paper_rows
    ]

    qualifications = [row.qualification for row in paper_rows]
    open_rows = [row for row in paper_rows if row.summary.open_trade is not None]
    research_pnl = sum(row.summary.total_pnl_eur for row in paper_rows)
    research_r = sum(row.summary.total_r for row in paper_rows)
    legacy_pnl = sum(row.summary.legacy_pnl_eur for row in paper_rows)
    legacy_r = sum(row.summary.legacy_total_r for row in paper_rows)
    legacy_trades = sum(row.summary.legacy_trades for row in paper_rows)
    research_open_risk = sum(
        row.summary.open_trade.risk_eur
        for row in open_rows
        if row.summary.open_trade is not None
    )

    eligible = [
        row
        for row in paper_rows
        if admissions.get(row.strategy_id) is not None
        and admissions[row.strategy_id].state == AdmissionState.ACTIVE
        and row.qualification.state == ProspectiveQualificationState.SUPPORTS_DEMO
    ]

    collection_rows = [
        row
        for row in open_rows
        if demo_collection_allowed(admissions.get(row.strategy_id))
    ]

    selected_row: PaperStrategyRuntime | None = None
    if eligible:
        selected_row = max(
            eligible,
            key=lambda row: (
                row.qualification.expectancy_r,
                row.qualification.profit_factor,
                -row.qualification.max_drawdown_r,
            ),
        )
        action = PortfolioAction.DEMO_ELIGIBLE
        selected = selected_row.strategy_id
        historical_active = True
        prospective_supports_demo = True
        reason = (
            "historical ACTIVE admission and prospective paper evidence "
            "support demo evaluation"
        )
    elif collection_rows:
        selected_row = max(
            collection_rows,
            key=lambda row: (
                admissions[row.strategy_id].weakest_expectancy_r,
                row.qualification.expectancy_r,
                -row.summary.open_trade.risk_eur
                if row.summary.open_trade is not None
                else 0.0,
            ),
        )
        action = PortfolioAction.DEMO_COLLECTION
        selected = selected_row.strategy_id
        historical_active = False
        prospective_supports_demo = (
            selected_row.qualification.state
            == ProspectiveQualificationState.SUPPORTS_DEMO
        )
        reason = (
            "paper-collection candidate has an executable paper trade; "
            "eligible for isolated broker DEMO collection"
        )
    elif open_rows:
        selected_row = open_rows[0]
        action = PortfolioAction.PAPER_ONLY
        selected = selected_row.strategy_id
        historical_active = (
            admissions.get(selected_row.strategy_id) is not None
            and admissions[selected_row.strategy_id].state == AdmissionState.ACTIVE
        )
        prospective_supports_demo = (
            selected_row.qualification.state
            == ProspectiveQualificationState.SUPPORTS_DEMO
        )
        reason = "paper position is open; broker execution remains locked"
    else:
        action = PortfolioAction.NO_TRADE
        selected = None
        historical_active = any(
            decision.state == AdmissionState.ACTIVE
            for decision in admissions.values()
        )
        prospective_supports_demo = any(
            row.qualification.state
            == ProspectiveQualificationState.SUPPORTS_DEMO
            for row in paper_rows
        )
        reason = (
            "no strategy satisfies both historical ACTIVE admission and "
            "prospective paper qualification"
        )

    selected_daily_pnl = selected_row.daily_pnl_eur if selected_row else 0.0
    selected_daily_r = selected_row.daily_r if selected_row else 0.0
    selected_open_risk = (
        selected_row.summary.open_trade.risk_eur
        if selected_row is not None and selected_row.summary.open_trade is not None
        else 0.0
    )
    selected_open_positions = (
        1
        if selected_row is not None and selected_row.summary.open_trade is not None
        else 0
    )

    max_daily_loss = (
        settings.reference_capital_eur * settings.max_daily_loss_fraction
    )
    remaining = max(0.0, max_daily_loss + min(0.0, selected_daily_pnl))

    return TradingOverview(
        at=now,
        broker=read_broker_demo_snapshot(files_dir),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=settings.reference_capital_eur,
            research_paper_closed_pnl_eur=research_pnl,
            research_paper_total_r=research_r,
            research_paper_legacy_closed_pnl_eur=legacy_pnl,
            research_paper_legacy_total_r=legacy_r,
            research_paper_legacy_trades=legacy_trades,
            research_paper_open_risk_eur=research_open_risk,
            research_paper_open_positions=len(open_rows),
            selected_daily_pnl_eur=selected_daily_pnl,
            selected_daily_r=selected_daily_r,
            selected_open_risk_eur=selected_open_risk,
            selected_open_positions=selected_open_positions,
            max_daily_loss_eur=max_daily_loss,
            remaining_daily_loss_budget_eur=remaining,
        ),
        portfolio=PortfolioDecision(
            at=now,
            action=action,
            selected_strategy_id=selected,
            reason=reason,
            historical_active=historical_active,
            prospective_supports_demo=prospective_supports_demo,
        ),
        qualifications=qualifications,
        paper_strategies=paper_rows,
    )
