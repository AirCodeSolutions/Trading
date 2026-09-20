from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.config import ExecutionMode, settings
from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.macro import MacroGateStatus
from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import (
    BrokerDemoSnapshot,
    PaperStrategyRuntime,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualification,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.domain.shadow_paper import (
    PaperTradeStatus,
    ShadowPaperSummary,
    ShadowPaperTrade,
)
from app.domain.trading import Side
from app.services.demo_execution import (
    read_pending_command,
    submit_selected_demo_order,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 19, 18, 30, tzinfo=TZ)
STRATEGY = "BTCUSD:break_retest_reaccel"


def open_trade() -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id="trade-1",
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=Side.BUY,
        signal_at=NOW,
        entry_bar_at=NOW,
        opened_at=NOW,
        entry_price=81000,
        stop_price=80800,
        target_price=81360,
        spread_at_entry=20,
        lots=0.01,
        risk_eur=2,
        risk_distance=200,
        target_r=1.8,
        max_holding_bars=18,
        status=PaperTradeStatus.OPEN,
    )


def overview() -> TradingOverview:
    qualification = ProspectiveQualification(
        strategy_id=STRATEGY,
        state=ProspectiveQualificationState.SUPPORTS_DEMO,
        closed_trades=20,
        expectancy_r=0.2,
        profit_factor=1.4,
        max_drawdown_r=3,
        reason="test",
    )
    summary = ShadowPaperSummary(
        closed_trades=20,
        wins=12,
        losses=8,
        total_r=4,
        expectancy_r=0.2,
        profit_factor=1.4,
        max_drawdown_r=3,
        total_pnl_eur=8,
        open_trade=open_trade(),
    )
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=100000,
            equity=100000,
            margin=0,
            free_margin=100000,
            observed_positions=0,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=200,
            research_paper_closed_pnl_eur=8,
            research_paper_total_r=4,
            research_paper_open_risk_eur=2,
            research_paper_open_positions=1,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=2,
            selected_open_positions=1,
            max_daily_loss_eur=6,
            remaining_daily_loss_budget_eur=6,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.DEMO_ELIGIBLE,
            selected_strategy_id=STRATEGY,
            reason="test",
            historical_active=True,
            prospective_supports_demo=True,
        ),
        qualifications=[qualification],
        paper_strategies=[
            PaperStrategyRuntime(
                strategy_id=STRATEGY,
                symbol="BTCUSD",
                mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
                summary=summary,
                qualification=qualification,
            )
        ],
    )


def proposal() -> ExecutionProposal:
    return ExecutionProposal(
        id="proposal-1",
        symbol="BTCUSD",
        timeframe="M5",
        side=Side.BUY,
        strategy_id=STRATEGY,
        at=NOW,
        reason="test",
        status=ProposalStatus.AUTHORIZED,
    )


def clear_macro() -> MacroGateStatus:
    return MacroGateStatus(
        at=NOW,
        blocked=False,
        active_events=[],
        reason="clear",
    )


def test_demo_submit_refuses_while_execution_mode_is_paper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.PAPER)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)

    with pytest.raises(ValueError, match="execution mode is not demo"):
        submit_selected_demo_order(
            files_dir=tmp_path,
            overview=overview(),
            macro=clear_macro(),
            proposal=proposal(),
            now=NOW,
        )

    assert not (tmp_path / "trading_demo_command.csv").exists()


def test_demo_submit_writes_command_only_when_all_guards_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)

    command = submit_selected_demo_order(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        proposal=proposal(),
        now=NOW,
    )
    parsed = read_pending_command(tmp_path / "trading_demo_command.csv")

    assert parsed is not None
    assert parsed.command_id == command.command_id
    assert parsed.symbol == "BTCUSD"
    assert parsed.strategy_id == STRATEGY
    assert parsed.stop_loss == 80800
    assert parsed.take_profit == 81360


def test_demo_submit_refuses_when_broker_already_has_position(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.broker.observed_positions = 1

    with pytest.raises(ValueError, match="broker already has open positions"):
        submit_selected_demo_order(
            files_dir=tmp_path,
            overview=current,
            macro=clear_macro(),
            proposal=proposal(),
            now=NOW,
        )


def test_demo_submit_refuses_when_daily_loss_budget_is_exhausted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.risk.remaining_daily_loss_budget_eur = 0

    with pytest.raises(ValueError, match="daily loss budget is exhausted"):
        submit_selected_demo_order(
            files_dir=tmp_path,
            overview=current,
            macro=clear_macro(),
            proposal=proposal(),
            now=NOW,
        )
