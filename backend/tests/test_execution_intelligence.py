from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.approval import ProposalStatus
from app.domain.demo_execution import (
    DemoBridgeCommandStatus,
    DemoBridgeResult,
    DemoCloseCommand,
    DemoOrderCommand,
)
from app.domain.portfolio import (
    BrokerDemoSnapshot,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualification,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.domain.trading import Side
from app.services.execution_audit import (
    append_bridge_result_if_new,
    append_close_command_event,
    append_open_command_event,
    build_execution_quality_summary,
    load_execution_audit_events,
)
from app.services.qualification_history import (
    load_qualification_history,
    record_qualification_history,
)

TZ=ZoneInfo("Europe/Athens")
NOW=datetime(2026,9,22,12,0,tzinfo=TZ)


def test_execution_audit_pairs_command_and_fill(tmp_path: Path) -> None:
    path=tmp_path/"audit.jsonl"
    command=DemoOrderCommand(
        command_id="cmd-1",
        symbol="EURUSD",
        side=Side.BUY,
        lots=0.04,
        stop_loss=1.0990,
        take_profit=1.1020,
        strategy_id="manual_demo:eurusd",
        issued_at=NOW,
        magic_number=560619,
        slippage_points=20,
        proposal_status=ProposalStatus.AUTHORIZED,
    )
    append_open_command_event(
        path,
        command,
        reference_entry_price=1.1000,
        reference_risk_eur=4.0,
    )
    result=DemoBridgeResult(
        command_id="cmd-1",
        status=DemoBridgeCommandStatus.FILLED,
        ticket=123,
        fill_price=1.1002,
        stop_loss=1.0990,
        take_profit=1.1020,
        processed_at="2026.09.22 12:00:01",
    )
    first=append_bridge_result_if_new(path,result,at=NOW)
    second=append_bridge_result_if_new(path,result,at=NOW)

    assert first is not None
    assert second is None
    assert len(load_execution_audit_events(path))==2
    summary=build_execution_quality_summary(path)
    assert summary.commands==1
    assert summary.fills==1
    assert summary.refused==0
    assert len(summary.samples)==1
    sample=summary.samples[0]
    assert round(sample.adverse_slippage_price,6)==0.0002
    assert round(sample.slippage_r,3)==0.2
    assert sample.reference_risk_eur == 4.0
    assert round(sample.fill_risk_eur or 0, 3) == 4.8
    assert round(sample.risk_delta_eur or 0, 3) == 0.8
    assert round(sample.risk_delta_pct or 0, 3) == 20.0
    assert round(summary.average_risk_delta_eur, 3) == 0.8
    assert round(summary.max_risk_increase_eur, 3) == 0.8
    assert round(summary.max_risk_increase_pct, 3) == 20.0
    assert round(sample.reference_reward_risk_ratio or 0, 3) == 2.0
    assert round(sample.fill_reward_risk_ratio or 0, 3) == 1.5
    assert round(sample.rr_delta or 0, 3) == -0.5
    assert round(summary.average_rr_delta, 3) == -0.5
    assert round(summary.minimum_fill_reward_risk_ratio, 3) == 1.5


def _overview(qualification: ProspectiveQualification) -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=850000,
            equity=850000,
            margin=0,
            free_margin=850000,
            observed_positions=0,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=400,
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=0,
            research_paper_open_positions=0,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=12,
            remaining_daily_loss_budget_eur=12,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.NO_TRADE,
            reason="waiting",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[qualification],
        paper_strategies=[],
    )


def test_qualification_history_records_only_meaningful_changes(tmp_path: Path) -> None:
    path=tmp_path/"qualification.jsonl"
    q1=ProspectiveQualification(
        strategy_id="GBPUSD:directional_pullback_resumption",
        state=ProspectiveQualificationState.COLLECTING,
        closed_trades=3,
        expectancy_r=0.2,
        profit_factor=1.4,
        max_drawdown_r=1.0,
        reason="insufficient prospective paper evidence",
    )
    assert len(record_qualification_history(path,_overview(q1),at=NOW))==1
    assert len(record_qualification_history(path,_overview(q1),at=NOW))==0

    q2=q1.model_copy(update={"closed_trades":4,"expectancy_r":0.25})
    assert len(record_qualification_history(path,_overview(q2),at=NOW))==1
    rows=load_qualification_history(path)
    assert [row.closed_trades for row in rows]==[3,4]


def test_execution_quality_counts_close_fill_without_slippage_sample(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    open_command = DemoOrderCommand(
        command_id="open-1",
        symbol="EURUSD",
        side=Side.BUY,
        lots=0.04,
        stop_loss=1.0990,
        take_profit=1.1020,
        strategy_id="manual_demo:eurusd",
        issued_at=NOW,
        magic_number=560619,
        slippage_points=20,
        proposal_status=ProposalStatus.AUTHORIZED,
    )
    append_open_command_event(
        path,
        open_command,
        reference_entry_price=1.1000,
    )
    append_bridge_result_if_new(
        path,
        DemoBridgeResult(
            command_id="open-1",
            status=DemoBridgeCommandStatus.FILLED,
            ticket=321,
            fill_price=1.1002,
            stop_loss=1.0990,
            take_profit=1.1020,
            processed_at="2026.09.22 12:00:01",
        ),
        at=NOW,
    )

    close_command = DemoCloseCommand(
        command_id="close-1",
        ticket=321,
        symbol="EURUSD",
        strategy_id="manual_demo:eurusd",
        issued_at=NOW,
        magic_number=560619,
        slippage_points=20,
    )
    append_close_command_event(path, close_command)
    append_bridge_result_if_new(
        path,
        DemoBridgeResult(
            command_id="close-1",
            status=DemoBridgeCommandStatus.FILLED,
            ticket=321,
            fill_price=1.1010,
            processed_at="2026.09.22 12:30:00",
        ),
        at=NOW,
    )

    summary = build_execution_quality_summary(path)

    assert summary.commands == 2
    assert summary.fills == 2
    assert summary.unpaired_results == 0
    assert len(summary.samples) == 1
