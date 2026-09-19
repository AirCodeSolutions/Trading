from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.admission import AdmissionState
from app.domain.portfolio import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.services.broker_account import read_broker_demo_snapshot
from app.services.paper_registry import load_paper_registry
from app.services.runtime_admission_registry import load_research_admissions


def build_trading_overview(
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
) -> TradingOverview:
    paper_rows = load_paper_registry(runtime_dir)
    admissions = load_research_admissions(runtime_dir / "strategy_admissions.json")

    qualifications = [row.qualification for row in paper_rows]
    open_rows = [row for row in paper_rows if row.summary.open_trade is not None]
    total_pnl = sum(row.summary.total_pnl_eur for row in paper_rows)
    total_r = sum(row.summary.total_r for row in paper_rows)
    open_risk = sum(
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

    if eligible:
        winner = max(
            eligible,
            key=lambda row: (
                row.qualification.expectancy_r,
                row.qualification.profit_factor,
                -row.qualification.max_drawdown_r,
            ),
        )
        action = PortfolioAction.DEMO_ELIGIBLE
        selected = winner.strategy_id
        historical_active = True
        prospective_supports_demo = True
        reason = (
            "historical ACTIVE admission and prospective paper evidence "
            "support demo evaluation"
        )
    elif open_rows:
        winner = open_rows[0]
        action = PortfolioAction.PAPER_ONLY
        selected = winner.strategy_id
        historical_active = (
            admissions.get(winner.strategy_id) is not None
            and admissions[winner.strategy_id].state == AdmissionState.ACTIVE
        )
        prospective_supports_demo = (
            winner.qualification.state
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

    max_daily_loss = (
        settings.reference_capital_eur * settings.max_daily_loss_fraction
    )
    remaining = max(0.0, max_daily_loss + min(0.0, total_pnl))

    return TradingOverview(
        at=now,
        broker=read_broker_demo_snapshot(files_dir),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=settings.reference_capital_eur,
            paper_closed_pnl_eur=total_pnl,
            paper_total_r=total_r,
            paper_open_risk_eur=open_risk,
            paper_open_positions=len(open_rows),
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
