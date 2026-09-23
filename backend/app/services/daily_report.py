from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.domain.daily_report import (
    AssetResearchState,
    AssetResearchStatus,
    DailyTradingReport,
)
from app.domain.demo_execution import DemoExecutionStatus
from app.domain.portfolio import TradingOverview
from app.domain.trading_intelligence import (
    OpportunityCaptureState,
    TradingIntelligenceOverview,
)
from app.services.broker_history import summarize_trading_new_closed_tickets
from app.services.demo_execution import build_demo_status
from app.services.execution_audit import (
    AUDIT_FILE,
    build_execution_quality_summary,
)
from app.services.macro_gate import macro_gate_status
from app.services.portfolio_overview import build_trading_overview
from app.services.trading_intelligence import build_trading_intelligence


def build_daily_trading_report(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now,
    overview: TradingOverview | None = None,
    intelligence: TradingIntelligenceOverview | None = None,
    demo: DemoExecutionStatus | None = None,
) -> DailyTradingReport:
    if overview is None:
        overview = build_trading_overview(files_dir, runtime_dir, now)
    if intelligence is None:
        intelligence = build_trading_intelligence(
            files_dir,
            runtime_dir,
            now=now,
            window_hours=24,
            symbols=settings.session_watch_symbols,
        )
    if demo is None:
        demo = build_demo_status(
            files_dir=files_dir,
            overview=overview,
            macro=macro_gate_status(settings.macro_events_path, now),
            now=now,
        )
    quality=build_execution_quality_summary(runtime_dir/AUDIT_FILE)
    broker_closed = summarize_trading_new_closed_tickets(
        files_dir,
        runtime_dir / AUDIT_FILE,
        magic_number=settings.demo_magic_number,
        report_date=now.date(),
    )
    asset_rows=[]
    by_symbol={row.symbol:row for row in intelligence.assets}
    for symbol in settings.session_watch_symbols:
        paper_rows=[row for row in overview.paper_strategies if row.symbol==symbol]
        eligible=[row.strategy_id for row in paper_rows if row.paper_entry_allowed]
        qualification_states={row.strategy_id:row.qualification.state for row in paper_rows}
        intel=by_symbol.get(symbol)
        market=intel.market_opportunities if intel else 0
        captured=(intel.captured_executable+intel.captured_blocked) if intel else 0
        missed=intel.missed_opportunities if intel else 0
        blocked_expectancy=(
            intel.blocked_total_r/intel.blocked_closed_probes
            if intel and intel.blocked_closed_probes
            else 0.0
        )
        failed = [
            row.strategy_id
            for row in paper_rows
            if row.qualification.state.value == "failed"
        ]
        if eligible:
            state=AssetResearchState.COLLECT_PROSPECTIVE
            next_action="collect prospective PAPER/DEMO evidence without changing the admitted mechanism"
        elif failed:
            state=AssetResearchState.DEGRADED
            next_action="prospective evidence FAILED: keep new entries frozen and diagnose before any re-admission"
        else:
            state=AssetResearchState.RESEARCH_ONLY
            next_action="research a distinct market-first mechanism; do not relax execution guards"
        asset_rows.append(
            AssetResearchStatus(
                symbol=symbol,
                state=state,
                paper_eligible_strategies=eligible,
                qualification_states=qualification_states,
                market_opportunities_24h=market,
                captured_opportunities_24h=captured,
                missed_opportunities_24h=missed,
                capture_rate_24h=(captured/market) if market else 0.0,
                blocked_expectancy_r_24h=blocked_expectancy,
                next_action=next_action,
            )
        )
    qcounts=Counter(item.state for item in overview.qualifications)
    captured_total=sum(
        row.capture_state!=OpportunityCaptureState.MISSED
        for row in intelligence.opportunities
    )
    missed_total=sum(
        row.capture_state==OpportunityCaptureState.MISSED
        for row in intelligence.opportunities
    )
    return DailyTradingReport(
        report_date=now.date(),
        generated_at=now,
        reference_capital_eur=overview.risk.reference_capital_eur,
        execution_mode=settings.execution_mode.value,
        live_trading_enabled=settings.live_trading_enabled,
        broker_is_demo=bool(overview.broker and overview.broker.is_demo),
        portfolio_action=overview.portfolio.action,
        portfolio_reason=overview.portfolio.reason,
        paper_closed_pnl_eur_today=sum(
            row.daily_pnl_eur for row in overview.paper_strategies
        ),
        paper_closed_r_today=sum(
            row.daily_r for row in overview.paper_strategies
        ),
        paper_open_positions=overview.risk.research_paper_open_positions,
        paper_open_risk_eur=overview.risk.research_paper_open_risk_eur,
        bridge_open_positions=len(demo.bridge_positions),
        bridge_unrealized_pnl_eur=sum(row.profit for row in demo.bridge_positions),
        broker_realized_pnl_eur_today=(
            broker_closed.realized_pnl_eur if broker_closed.complete else None
        ),
        broker_closed_trades_today=broker_closed.trades,
        broker_history_complete=broker_closed.complete,
        market_opportunities_24h=len(intelligence.opportunities),
        captured_opportunities_24h=captured_total,
        missed_opportunities_24h=missed_total,
        qualification_counts=dict(qcounts),
        execution_quality=quality,
        assets=asset_rows,
        limitations=[
            *(
                [
                    (
                        "broker realized PnL is incomplete: closed Trading-New "
                        f"tickets missing from MT4 history {broker_closed.missing_tickets}"
                    )
                ]
                if not broker_closed.complete
                else []
            ),
            *intelligence.limitations,
        ],
    )


def write_daily_trading_report(
    runtime_dir: Path,
    report: DailyTradingReport,
) -> None:
    runtime_dir.mkdir(parents=True,exist_ok=True)
    payload=report.model_dump_json(indent=2)
    for path in (
        runtime_dir/"daily_report_latest.json",
        runtime_dir/f"daily_report_{report.report_date.isoformat()}.json",
    ):
        temp=path.with_suffix(path.suffix+".tmp")
        temp.write_text(payload,encoding="utf-8")
        temp.replace(path)


def load_daily_trading_report(path: Path) -> DailyTradingReport | None:
    if not path.is_file():
        return None
    try:
        return DailyTradingReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
