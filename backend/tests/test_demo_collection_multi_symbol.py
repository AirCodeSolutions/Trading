from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import ExecutionMode, settings
from app.domain.admission import AdmissionState
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
from app.services.demo_collection import advance_demo_collection
from app.services.demo_execution import read_pending_command

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 24, 11, 15, tzinfo=TZ)


def _paper_row(
    strategy_id: str,
    symbol: str,
    mechanism: OpportunityMechanism,
    *,
    entry: float,
    stop: float,
    target: float,
) -> PaperStrategyRuntime:
    trade = ShadowPaperTrade(
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
        spread_at_entry=0.1,
        lots=0.5,
        risk_eur=8738,
        risk_distance=entry - stop,
        target_r=1.5,
        max_holding_bars=12,
    )
    q = ProspectiveQualification(
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
        qualification=q,
        historical_state=AdmissionState.SHADOW,
        paper_entry_allowed=True,
    )


def _overview() -> TradingOverview:
    btc = _paper_row(
        "BTCUSD:structural_displacement_sequence",
        "BTCUSD",
        OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        entry=86000,
        stop=85600,
        target=86600,
    )
    xau = _paper_row(
        "XAUUSD:asia_range_sweep_reversal",
        "XAUUSD",
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        entry=4285,
        stop=4279,
        target=4294,
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
            selected_strategy_id="BTCUSD:structural_displacement_sequence",
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[btc.qualification, xau.qualification],
        paper_strategies=[btc, xau],
    )


def test_auto_collection_opens_xau_while_btc_ticket_is_already_open(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "demo_collection_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (tmp_path / "trading_demo_positions.csv").write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        "101,BTCUSD,BUY,0.5,86000,85600,86600,0,2026.09.24 11:00,"
        "TradingNew:BTCUSD:structural_displacement_sequence\n",
        encoding="utf-8",
    )

    advance_demo_collection(
        tmp_path,
        runtime,
        _overview(),
        MacroGateStatus(
            at=NOW,
            blocked=False,
            active_events=[],
            reason="clear",
        ),
        NOW,
    )

    command = read_pending_command(tmp_path / "trading_demo_command.csv")
    assert command is not None
    assert command.symbol == "XAUUSD"
    assert command.strategy_id == "XAUUSD:asia_range_sweep_reversal"
