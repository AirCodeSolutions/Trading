from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.portfolio import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.services.broker_account import read_broker_demo_snapshot
from app.services.prospective_qualification import assess_prospective
from app.services.shadow_paper import load_shadow_paper_summary


BTC_BREAK_RETEST_STRATEGY_ID = "BTCUSD:break_retest_reaccel"


def build_trading_overview(
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
) -> TradingOverview:
    state_path = runtime_dir / "BTCUSD_break_retest_paper_state.json"
    trades_path = runtime_dir / "BTCUSD_break_retest_paper_trades.jsonl"
    paper = load_shadow_paper_summary(state_path, trades_path)
    qualification = assess_prospective(BTC_BREAK_RETEST_STRATEGY_ID, paper)

    # Historical admission is intentionally not inferred from paper evidence.
    # No strategy is currently persisted as ACTIVE in the runtime registry.
    historical_active = False
    prospective_supports_demo = (
        qualification.state == ProspectiveQualificationState.SUPPORTS_DEMO
    )
    if historical_active and prospective_supports_demo:
        action = PortfolioAction.DEMO_ELIGIBLE
        selected = BTC_BREAK_RETEST_STRATEGY_ID
        reason = "historical and prospective evidence both support demo evaluation"
    elif paper.open_trade is not None:
        action = PortfolioAction.PAPER_ONLY
        selected = BTC_BREAK_RETEST_STRATEGY_ID
        reason = "paper trade is open; broker execution remains locked"
    else:
        action = PortfolioAction.NO_TRADE
        selected = None
        reason = "no strategy satisfies both historical and prospective qualification"

    open_risk = paper.open_trade.risk_eur if paper.open_trade is not None else 0.0
    max_daily_loss = (
        settings.reference_capital_eur * settings.max_daily_loss_fraction
    )
    remaining = max(0.0, max_daily_loss + min(0.0, paper.total_pnl_eur))

    return TradingOverview(
        at=now,
        broker=read_broker_demo_snapshot(files_dir),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=settings.reference_capital_eur,
            paper_closed_pnl_eur=paper.total_pnl_eur,
            paper_total_r=paper.total_r,
            paper_open_risk_eur=open_risk,
            paper_open_positions=1 if paper.open_trade is not None else 0,
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
        qualifications=[qualification],
    )
