from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import ExecutionMode, settings
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
from app.services.demo_collection import advance_demo_collection, load_demo_collection_state
from app.services.demo_execution import read_pending_close_command, read_pending_command

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 21, 17, 0, tzinfo=TZ)
STRATEGY = "GBPUSD:directional_pullback_resumption"


def trade(*, status: PaperTradeStatus = PaperTradeStatus.OPEN) -> ShadowPaperTrade:
    closed = status != PaperTradeStatus.OPEN
    return ShadowPaperTrade(
        trade_id="paper-1",
        symbol="GBPUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        side=Side.BUY,
        signal_at=NOW,
        entry_bar_at=NOW,
        opened_at=NOW,
        entry_price=1.3400,
        stop_price=1.3380,
        target_price=1.3430,
        spread_at_entry=0.00011,
        lots=0.01,
        risk_eur=2.0,
        risk_distance=0.002,
        target_r=1.5,
        max_holding_bars=12,
        status=status,
        exit_at=NOW + timedelta(hours=1) if closed else None,
        exit_price=1.3410 if closed else None,
        result_r=0.5 if closed else None,
        pnl_eur=1.0 if closed else None,
        bars_held=12 if closed else 0,
    )


def overview(open_trade: ShadowPaperTrade | None) -> TradingOverview:
    qualification = ProspectiveQualification(
        strategy_id=STRATEGY,
        state=ProspectiveQualificationState.COLLECTING,
        closed_trades=0,
        expectancy_r=0,
        profit_factor=0,
        max_drawdown_r=0,
        reason="collecting",
    )
    summary = ShadowPaperSummary(
        closed_trades=0,
        wins=0,
        losses=0,
        total_r=0,
        expectancy_r=0,
        profit_factor=0,
        max_drawdown_r=0,
        total_pnl_eur=0,
        open_trade=open_trade,
    )
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=850000,
            equity=850000,
            margin=0,
            free_margin=850000,
            observed_positions=2,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=200,
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=2 if open_trade else 0,
            research_paper_open_positions=1 if open_trade else 0,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=2 if open_trade else 0,
            selected_open_positions=1 if open_trade else 0,
            max_daily_loss_eur=6,
            remaining_daily_loss_budget_eur=6,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.DEMO_COLLECTION if open_trade else PortfolioAction.NO_TRADE,
            selected_strategy_id=STRATEGY if open_trade else None,
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[qualification],
        paper_strategies=[
            PaperStrategyRuntime(
                strategy_id=STRATEGY,
                symbol="GBPUSD",
                mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
                summary=summary,
                qualification=qualification,
                historical_state="shadow",
                paper_collection_candidate=True,
            )
        ],
    )


def macro() -> MacroGateStatus:
    return MacroGateStatus(at=NOW, blocked=False, active_events=[], reason="clear")


def enable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)


def test_demo_collection_writes_open_once_for_same_paper_trade(tmp_path: Path, monkeypatch) -> None:
    enable(monkeypatch)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    current = overview(trade())

    advance_demo_collection(tmp_path, runtime, current, macro(), NOW)
    first = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert first is not None

    advance_demo_collection(tmp_path, runtime, current, macro(), NOW + timedelta(seconds=30))
    second = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert second is not None
    assert second.command_id == first.command_id
    state = load_demo_collection_state(runtime / "demo_collection_state.json")
    assert state.paper_trade_id == "paper-1"
    assert state.open_command_id == first.command_id


def test_demo_collection_closes_remaining_bridge_ticket_after_paper_timeout(tmp_path: Path, monkeypatch) -> None:
    enable(monkeypatch)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    opened = overview(trade())
    advance_demo_collection(tmp_path, runtime, opened, macro(), NOW)
    open_command = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert open_command is not None
    (tmp_path / "trading_demo_command.csv").unlink()
    (tmp_path / "trading_demo_result.csv").write_text(
        f"{open_command.command_id},FILLED,321,0,1.3400,1.3380,1.3430,2026.09.21 17:00:01\n",
        encoding="utf-8",
    )
    (tmp_path / "trading_demo_positions.csv").write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        "321,GBPUSD,BUY,0.01,1.3400,1.3380,1.3430,0,2026.09.21 17:00,TradingNew:GBPUSD\n",
        encoding="utf-8",
    )
    closed = trade(status=PaperTradeStatus.TIMEOUT)
    (runtime / "GBPUSD_directional_pullback_paper_trades.jsonl").write_text(
        closed.model_dump_json() + "\n",
        encoding="utf-8",
    )

    advance_demo_collection(tmp_path, runtime, overview(None), macro(), NOW + timedelta(hours=1))

    close_command = read_pending_close_command(tmp_path / "trading_demo_close_command.csv")
    assert close_command is not None
    assert close_command.ticket == 321
    assert close_command.symbol == "GBPUSD"
    assert close_command.strategy_id == STRATEGY


def test_demo_collection_does_not_reopen_failed_trade(tmp_path: Path, monkeypatch) -> None:
    enable(monkeypatch)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    current = overview(trade())
    advance_demo_collection(tmp_path, runtime, current, macro(), NOW)
    command = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert command is not None
    (tmp_path / "trading_demo_command.csv").unlink()
    (tmp_path / "trading_demo_result.csv").write_text(
        f"{command.command_id},REFUSED,0,9107,0,1.3380,1.3430,2026.09.21 17:00:01\n",
        encoding="utf-8",
    )

    advance_demo_collection(tmp_path, runtime, current, macro(), NOW + timedelta(seconds=30))

    assert not (tmp_path / "trading_demo_command.csv").exists()
    state = load_demo_collection_state(runtime / "demo_collection_state.json")
    assert state.last_completed_trade_id == "paper-1"
    assert state.last_error is not None


def test_demo_collection_drain_blocks_new_open_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    enable(monkeypatch)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    current = overview(trade())

    advance_demo_collection(
        tmp_path,
        runtime,
        current,
        macro(),
        NOW,
        allow_new_entries=False,
    )

    assert read_pending_command(tmp_path / "trading_demo_command.csv") is None
    state = load_demo_collection_state(runtime / "demo_collection_state.json")
    assert state.paper_trade_id is None


def test_demo_collection_drain_still_allows_existing_close(
    tmp_path: Path,
    monkeypatch,
) -> None:
    enable(monkeypatch)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    opened = overview(trade())
    advance_demo_collection(tmp_path, runtime, opened, macro(), NOW)
    open_command = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert open_command is not None
    (tmp_path / "trading_demo_command.csv").unlink()
    (tmp_path / "trading_demo_result.csv").write_text(
        f"{open_command.command_id},FILLED,321,0,1.3400,1.3380,1.3430,2026.09.21 17:00:01\n",
        encoding="utf-8",
    )
    (tmp_path / "trading_demo_positions.csv").write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        "321,GBPUSD,BUY,0.01,1.3400,1.3380,1.3430,0,2026.09.21 17:00,TradingNew:GBPUSD\n",
        encoding="utf-8",
    )
    closed = trade(status=PaperTradeStatus.TIMEOUT)
    (runtime / "GBPUSD_directional_pullback_paper_trades.jsonl").write_text(
        closed.model_dump_json() + "\n",
        encoding="utf-8",
    )

    advance_demo_collection(
        tmp_path,
        runtime,
        overview(None),
        macro(),
        NOW + timedelta(hours=1),
        allow_new_entries=False,
    )

    close_command = read_pending_close_command(
        tmp_path / "trading_demo_close_command.csv"
    )
    assert close_command is not None
    assert close_command.ticket == 321
