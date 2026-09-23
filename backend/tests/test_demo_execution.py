from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.config import ExecutionMode, settings
from app.domain.admission import AdmissionState
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
    build_demo_guard,
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


def test_demo_guard_distinguishes_armed_transport_from_waiting_portfolio(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.portfolio.action = PortfolioAction.NO_TRADE
    current.portfolio.selected_strategy_id = None
    current.paper_strategies[0].historical_state = AdmissionState.SHADOW
    current.paper_strategies[0].paper_entry_allowed = True
    current.paper_strategies[0].summary.open_trade = None

    guard = build_demo_guard(
        current,
        clear_macro(),
        NOW,
        bridge_positions=[],
    )

    assert guard.ready is False
    assert guard.transport_armed is True
    assert guard.auto_collection_armed is True
    assert guard.waiting_for_qualified_trade is True
    assert guard.qualified_collectors == 1
    assert "portfolio is not demo eligible" in guard.reasons


def test_demo_guard_reports_collection_disarmed_separately(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", False)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.portfolio.action = PortfolioAction.NO_TRADE
    current.portfolio.selected_strategy_id = None
    current.paper_strategies[0].historical_state = AdmissionState.SHADOW
    current.paper_strategies[0].paper_entry_allowed = True
    current.paper_strategies[0].summary.open_trade = None

    guard = build_demo_guard(
        current,
        clear_macro(),
        NOW,
        bridge_positions=[],
    )

    assert guard.ready is False
    assert guard.transport_armed is True
    assert guard.auto_collection_armed is False
    assert guard.waiting_for_qualified_trade is False
    assert guard.qualified_collectors == 1


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


def test_demo_submit_ignores_positions_owned_by_other_mt4_systems(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.broker.observed_positions = 1

    command = submit_selected_demo_order(
        files_dir=tmp_path,
        overview=current,
        macro=clear_macro(),
        proposal=proposal(),
        now=NOW,
    )

    assert command.strategy_id == STRATEGY


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


def test_external_broker_positions_do_not_block_magic_scoped_demo_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.portfolio.action = PortfolioAction.DEMO_COLLECTION
    current.portfolio.historical_active = False
    current.broker.observed_positions = 2

    command = submit_selected_demo_order(
        files_dir=tmp_path,
        overview=current,
        macro=clear_macro(),
        proposal=proposal(),
        now=NOW,
    )

    assert command.strategy_id == STRATEGY


def test_magic_scoped_bridge_position_blocks_second_demo_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    current = overview()
    current.portfolio.action = PortfolioAction.DEMO_COLLECTION
    (tmp_path / "trading_demo_positions.csv").write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        "123,BTCUSD,BUY,0.01,81000,80800,81360,0,2026.09.19 18:30,TradingNew:test\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Trading-New bridge already has open position"):
        submit_selected_demo_order(
            files_dir=tmp_path,
            overview=current,
            macro=clear_macro(),
            proposal=proposal(),
            now=NOW,
        )
