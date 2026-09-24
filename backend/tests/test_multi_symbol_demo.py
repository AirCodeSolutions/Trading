from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import ExecutionMode, settings
from app.domain.admission import AdmissionState
from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.demo_execution import DemoBridgePosition
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
from app.domain.shadow_paper import ShadowPaperSummary, ShadowPaperTrade
from app.domain.trading import Side
from app.services.demo_execution import (
    build_demo_guard,
    read_pending_command,
    submit_selected_demo_order,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 24, 11, 0, tzinfo=TZ)


def _trade(
    strategy_id: str,
    symbol: str,
    mechanism: OpportunityMechanism,
    *,
    entry: float,
    stop: float,
    target: float,
) -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id=f"{strategy_id}-trade",
        symbol=symbol,
        mechanism=mechanism,
        side=Side.BUY,
        signal_at=NOW,
        entry_bar_at=NOW,
        opened_at=NOW,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        spread_at_entry=0.1 if symbol == "XAUUSD" else 20.0,
        lots=0.5,
        risk_eur=8738.0,
        risk_distance=entry - stop,
        target_r=1.5,
        max_holding_bars=12,
    )


def _row(
    strategy_id: str,
    symbol: str,
    mechanism: OpportunityMechanism,
    trade: ShadowPaperTrade,
) -> PaperStrategyRuntime:
    qualification = ProspectiveQualification(
        strategy_id=strategy_id,
        state=ProspectiveQualificationState.COLLECTING,
        closed_trades=0,
        expectancy_r=0,
        profit_factor=0,
        max_drawdown_r=0,
        reason="collecting",
    )
    return PaperStrategyRuntime(
        strategy_id=strategy_id,
        symbol=symbol,
        mechanism=mechanism,
        summary=ShadowPaperSummary(
            closed_trades=0,
            wins=0,
            losses=0,
            total_r=0,
            expectancy_r=0,
            profit_factor=0,
            max_drawdown_r=0,
            total_pnl_eur=0,
            open_trade=trade,
        ),
        qualification=qualification,
        historical_state=AdmissionState.SHADOW,
        paper_entry_allowed=True,
    )


def _overview() -> TradingOverview:
    btc_id = "BTCUSD:structural_displacement_sequence"
    xau_id = "XAUUSD:asia_range_sweep_reversal"
    btc = _row(
        btc_id,
        "BTCUSD",
        OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        _trade(
            btc_id,
            "BTCUSD",
            OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
            entry=86000,
            stop=85600,
            target=86600,
        ),
    )
    xau = _row(
        xau_id,
        "XAUUSD",
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        _trade(
            xau_id,
            "XAUUSD",
            OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
            entry=4285,
            stop=4279,
            target=4294,
        ),
    )
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=873859.85,
            equity=873859.85,
            margin=0,
            free_margin=873859.85,
            observed_positions=1,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=873859.85,
            reference_capital_source="broker_equity",
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=17476,
            research_paper_open_positions=2,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=8738,
            selected_open_positions=1,
            max_daily_loss_eur=26215.8,
            remaining_daily_loss_budget_eur=26215.8,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.DEMO_COLLECTION,
            selected_strategy_id=btc_id,
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[btc.qualification, xau.qualification],
        paper_strategies=[btc, xau],
    )


def _macro() -> MacroGateStatus:
    return MacroGateStatus(at=NOW, blocked=False, active_events=[], reason="clear")


def _enable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)


def _position(symbol: str, strategy_id: str, ticket: int = 1) -> DemoBridgePosition:
    return DemoBridgePosition(
        ticket=ticket,
        symbol=symbol,
        side=Side.BUY,
        lots=0.5,
        open_price=1,
        stop_loss=0.9,
        take_profit=1.1,
        profit=0,
        open_time="2026.09.24 11:00",
        strategy_comment=f"TradingNew:{strategy_id}",
    )


def test_demo_guard_allows_different_symbol_while_btc_is_open(monkeypatch) -> None:
    _enable(monkeypatch)
    current = _overview()
    guard = build_demo_guard(
        current,
        _macro(),
        NOW,
        bridge_positions=[
            _position("BTCUSD", "BTCUSD:structural_displacement_sequence")
        ],
        target_symbol="XAUUSD",
    )

    assert "Trading-New bridge already has open position" not in " ".join(
        guard.reasons
    )


def test_demo_guard_blocks_second_position_on_same_symbol(monkeypatch) -> None:
    _enable(monkeypatch)
    current = _overview()
    guard = build_demo_guard(
        current,
        _macro(),
        NOW,
        bridge_positions=[
            _position("BTCUSD", "BTCUSD:structural_displacement_sequence")
        ],
        target_symbol="BTCUSD",
    )

    assert any("BTCUSD" in reason for reason in guard.reasons)
    assert guard.ready is False


def test_submit_can_use_non_selected_eligible_strategy_on_free_symbol(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _enable(monkeypatch)
    current = _overview()
    (tmp_path / "trading_demo_positions.csv").write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        "100,BTCUSD,BUY,0.5,86000,85600,86600,0,2026.09.24 11:00,"
        "TradingNew:BTCUSD:structural_displacement_sequence\n",
        encoding="utf-8",
    )
    proposal = ExecutionProposal(
        id="xau-proposal",
        symbol="XAUUSD",
        timeframe="M5",
        side=Side.BUY,
        strategy_id="XAUUSD:asia_range_sweep_reversal",
        at=NOW,
        reason="test",
        status=ProposalStatus.AUTHORIZED,
    )

    command = submit_selected_demo_order(
        files_dir=tmp_path,
        overview=current,
        macro=_macro(),
        proposal=proposal,
        now=NOW,
    )

    assert command.symbol == "XAUUSD"
    assert command.strategy_id == "XAUUSD:asia_range_sweep_reversal"
    assert read_pending_command(tmp_path / "trading_demo_command.csv") is not None


def test_mt4_bridge_blocks_only_same_symbol() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "mt4"
        / "TradingDemoExecutionBridge.mq4"
    ).read_text(encoding="utf-8")

    assert "HasBridgePositionForSymbol(symbol)" in source
    assert "OrderSymbol() == symbol" in source
    assert "if(HasBridgePosition())" not in source
