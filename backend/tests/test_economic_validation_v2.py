from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.domain.champion_challengers import ChampionChallengerReport
from app.domain.demo_execution import DemoBridgePosition, DemoExecutionGuard, DemoExecutionStatus
from app.domain.economic_validation_v2 import EconomicEvidenceState
from app.domain.execution_audit import ExecutionQualitySummary
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_funnel import OpportunityFunnel
from app.domain.portfolio import (
    BrokerDemoSnapshot,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    TradingOverview,
)
from app.domain.portfolio_allocator import PortfolioOpportunityAllocationReport
from app.domain.position_manager import PositionManagerReport
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.main import app
from app.services.economic_validation_v2 import (
    build_economic_validation_report,
    summarize_trade_economics,
)

NOW = datetime(2026, 10, 1, 8, tzinfo=ZoneInfo("Europe/Athens"))


def trade(index: int, result_r: float) -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id=str(index),
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=Side.BUY,
        signal_at=NOW + timedelta(minutes=index),
        entry_bar_at=NOW + timedelta(minutes=index),
        opened_at=NOW + timedelta(minutes=index),
        entry_price=100,
        stop_price=99,
        target_price=102,
        spread_at_entry=0.1,
        lots=1,
        risk_eur=100,
        risk_distance=1,
        target_r=2,
        max_holding_bars=18,
        result_r=result_r,
        pnl_eur=100 * result_r,
    )


def overview() -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=10000,
            equity=10000,
            margin=0,
            free_margin=10000,
            observed_positions=0,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=10000,
            reference_capital_source="broker_equity",
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=0,
            research_paper_open_positions=0,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=300,
            remaining_daily_loss_budget_eur=300,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.NO_TRADE,
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[],
        paper_strategies=[],
    )


def funnel() -> OpportunityFunnel:
    return OpportunityFunnel(
        window_hours=168,
        window_start=NOW - timedelta(hours=168),
        window_end=NOW,
        reference_capital_eur=10000,
        base_risk_budget_eur=100,
        absolute_max_risk_budget_eur=200,
        signal_rows=0,
        blocked_signal_rows=0,
        executable_signal_rows=0,
        tracked_blocked_probes=0,
        resolved_blocked_probes=0,
        open_blocked_probes=0,
        blocked_wins=0,
        blocked_losses=0,
        blocked_total_r=0,
        blocked_expectancy_r=0,
        blocked_feasible_under_max_risk=0,
    )


def demo() -> DemoExecutionStatus:
    guard = DemoExecutionGuard(
        at=NOW,
        ready=False,
        execution_mode="demo",
        bridge_enabled=True,
        live_trading_enabled=False,
        broker_is_demo=True,
        portfolio_action=PortfolioAction.NO_TRADE,
        macro_blocked=False,
        reasons=[],
    )
    return DemoExecutionStatus(guard=guard)


def quality() -> ExecutionQualitySummary:
    return ExecutionQualitySummary(
        commands=0,
        fills=0,
        refused=0,
        errors=0,
        unpaired_results=0,
        average_adverse_slippage_price=0,
        max_adverse_slippage_price=0,
        average_slippage_r=0,
    )


def allocator() -> PortfolioOpportunityAllocationReport:
    return PortfolioOpportunityAllocationReport(
        at=NOW,
        ready=True,
        capital_eur=10000,
        capital_source="broker_equity",
        max_total_open_risk_fraction=0.02,
        max_total_open_risk_eur=200,
        reason="test",
    )


def validation_report(*, drain_enabled: bool = False, demo_status=None):
    return build_economic_validation_report(
        now=NOW,
        window_hours=168,
        trades=[],
        overview=overview(),
        funnel=funnel(),
        position_manager=PositionManagerReport(
            generated_at=NOW,
            window_hours=168,
            trades=0,
            pending=0,
        ),
        champions=ChampionChallengerReport(),
        execution_quality=quality(),
        allocator=allocator(),
        demo=demo_status or demo(),
        drain_enabled=drain_enabled,
        broker_realized_pnl_eur_today=0,
        broker_closed_trades_window=0,
        broker_realized_pnl_eur_window=0,
        broker_missing_tickets_window=[],
        broker_history_complete=True,
    )


def test_trade_economics_are_chronological_and_exact():
    result = summarize_trade_economics([trade(0, 1), trade(1, -1), trade(2, 2)])
    assert result.trades == 3
    assert result.total_r == 2
    assert result.expectancy_r == pytest.approx(2 / 3)
    assert result.profit_factor == 3
    assert result.max_drawdown_r == 1
    assert result.win_rate == pytest.approx(2 / 3)


def test_research_deploy_gate_is_separate_from_v2_authority():
    report = validation_report(drain_enabled=False)
    assert report.economic_state is EconomicEvidenceState.NO_EVIDENCE
    assert report.v2_authority_cutover_supported is False
    assert len(report.v2_authority_gaps) == 3
    assert report.deployment.book_flat is True
    assert report.deployment.research_stack_deploy_ready is False

    armed = validation_report(drain_enabled=True)
    assert armed.deployment.book_flat is True
    assert armed.deployment.research_stack_deploy_ready is True
    assert armed.v2_authority_cutover_supported is False


def test_open_bridge_position_makes_book_non_flat():
    position = DemoBridgePosition(
        ticket=42,
        symbol="XAUUSD",
        side=Side.BUY,
        lots=1,
        open_price=100,
        stop_loss=99,
        take_profit=102,
        profit=12,
        open_time="2026.10.01 08:00",
        strategy_comment="TradingNew:test",
    )
    status = demo().model_copy(update={"bridge_positions": [position]})
    report = validation_report(drain_enabled=True, demo_status=status)
    assert report.bridge_open_positions == 1
    assert report.deployment.book_flat is False
    assert report.deployment.research_stack_deploy_ready is False


def test_economic_validation_endpoint_bounds_hours_before_io():
    response = TestClient(app).get(
        "/api/v1/research/economic-validation/v2?hours=169"
    )
    assert response.status_code == 422
