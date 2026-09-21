from datetime import datetime
from itertools import pairwise
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.domain.admission import AdmissionDecision, StrategyEvidence
from app.domain.approval import ExecutionProposal, ExecutionProposalRequest
from app.domain.blocked_probe import BlockedProbeRuntime
from app.domain.broker import (
    BrokerSymbolSpec,
    MarketQualityRequest,
    MarketQualityResult,
    PositionSizeRequest,
    PositionSizeResult,
)
from app.domain.demo_execution import DemoExecutionStatus, DemoOrderCommand
from app.domain.live_market import LiveMarketQuote
from app.domain.macro import MacroGateStatus
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    Mt4OpportunityBacktestRequest,
    OpportunityBacktestConfig,
    OpportunityBacktestResult,
    PortfolioResearchRequest,
    PortfolioResearchResult,
)
from app.domain.portfolio import MarketUniverseAsset, TradingOverview
from app.domain.regime import RegimeSnapshot
from app.domain.session import SessionPreflight
from app.domain.shadow import ShadowCollectionResult, ShadowOpportunityDiagnostic
from app.domain.shadow_paper import ShadowPaperSummary
from app.services.admission import assess_strategy
from app.services.approval_gate import ApprovalGate
from app.services.blocked_probe_registry import load_blocked_probe_registry
from app.services.btc_break_retest_shadow import scan_btc_break_retest_shadow
from app.services.capital_risk import size_position
from app.services.demo_execution import build_demo_status, submit_selected_demo_order
from app.services.execution_cost_history import summarize_execution_costs
from app.services.live_market_quality import build_live_market_quality
from app.services.macro_gate import load_macro_events, macro_gate_status
from app.services.market_quality import assess_market
from app.services.market_store import MarketStore
from app.services.market_universe import build_market_universe
from app.services.mt4_csv import _server_timezone, read_mt4_csv, summarize_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_live_bars import read_closed_bar_snapshot
from app.services.mt4_live_quotes import read_live_market_quotes
from app.services.mt4_specs import get_mt4_symbol_spec, list_mt4_symbol_specs
from app.services.opportunity_backtester import run_opportunity_backtest
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.portfolio_overview import build_trading_overview
from app.services.regime import classify_regime
from app.services.runtime_admission_registry import save_research_admissions
from app.services.session_preflight import build_session_preflight
from app.services.shadow_collector import collect_btc_break_retest_once
from app.services.shadow_overview import load_shadow_overview
from app.services.shadow_paper import load_shadow_paper_summary

app = FastAPI(title=settings.app_name, version="0.4.0")
market_store = MarketStore()
approval_gate = ApprovalGate(settings.decision_mode)


def _mt4_files_dir() -> Path:
    if settings.mt4_files_dir is None:
        raise HTTPException(status_code=503, detail="MT4 files directory is not configured")
    return Path(settings.mt4_files_dir)


def _normalized_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not normalized.isalnum() or len(normalized) > 32:
        raise HTTPException(status_code=422, detail="invalid symbol")
    return normalized


@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get(
    f"{settings.api_prefix}/session/preflight",
    response_model=SessionPreflight,
)
def session_preflight() -> SessionPreflight:
    now = datetime.now(tz=_server_timezone())
    files_dir = _mt4_files_dir()
    overview = build_trading_overview(
        files_dir,
        settings.shadow_ledger_dir,
        now,
    )
    macro = macro_gate_status(settings.macro_events_path, now)
    demo = build_demo_status(
        files_dir=files_dir,
        overview=overview,
        macro=macro,
        now=now,
    )
    return build_session_preflight(
        files_dir=files_dir,
        runtime_dir=settings.shadow_ledger_dir,
        now=now,
        macro=macro,
        overview=overview,
        demo_execution_ready=demo.guard.ready,
        watch_symbols=settings.session_watch_symbols,
    )


@app.get(
    f"{settings.api_prefix}/macro/status",
    response_model=MacroGateStatus,
)
def macro_status() -> MacroGateStatus:
    return macro_gate_status(
        settings.macro_events_path,
        datetime.now(tz=_server_timezone()),
    )


@app.get(f"{settings.api_prefix}/config")
def runtime_config() -> dict[str, object]:
    return {
        "execution_mode": settings.execution_mode,
        "decision_mode": settings.decision_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "allowed_timeframes": settings.allowed_timeframes,
        "reference_capital_eur": settings.reference_capital_eur,
        "risk_per_trade_fraction": settings.risk_per_trade_fraction,
        "absolute_max_risk_fraction": settings.absolute_max_risk_fraction,
        "max_daily_loss_fraction": settings.max_daily_loss_fraction,
        "paper_evidence_cutover_at": settings.paper_evidence_cutover_at,
        "max_spread_to_stop": settings.max_spread_to_stop,
    }


@app.post(f"{settings.api_prefix}/risk/size", response_model=PositionSizeResult)
def risk_size(request: PositionSizeRequest) -> PositionSizeResult:
    return size_position(request)


@app.post(f"{settings.api_prefix}/markets/quality", response_model=MarketQualityResult)
def market_quality(request: MarketQualityRequest) -> MarketQualityResult:
    return assess_market(request)


@app.get(
    f"{settings.api_prefix}/market/mt4/universe",
    response_model=list[MarketUniverseAsset],
)
def mt4_market_universe() -> list[MarketUniverseAsset]:
    return build_market_universe(
        _mt4_files_dir(),
        datetime.now(tz=_server_timezone()),
    )


@app.get(
    f"{settings.api_prefix}/market/mt4/live",
    response_model=list[LiveMarketQuote],
)
def mt4_live_market_quotes() -> list[LiveMarketQuote]:
    return read_live_market_quotes(
        _mt4_files_dir(),
        datetime.now(tz=_server_timezone()),
    )


@app.get(
    f"{settings.api_prefix}/market/mt4/quality",
    response_model=list[MarketQualityResult],
)
def mt4_live_market_quality() -> list[MarketQualityResult]:
    return build_live_market_quality(
        _mt4_files_dir(),
        datetime.now(tz=_server_timezone()),
        settings.session_watch_symbols,
    )


@app.get(f"{settings.api_prefix}/market/mt4/costs")
def mt4_execution_costs() -> dict[str, dict[str, float | int]]:
    return summarize_execution_costs(
        settings.shadow_ledger_dir / "execution_costs.jsonl"
    )


@app.get(
    f"{settings.api_prefix}/portfolio/overview",
    response_model=TradingOverview,
)
def portfolio_overview() -> TradingOverview:
    return build_trading_overview(
        _mt4_files_dir(),
        settings.shadow_ledger_dir,
        datetime.now(tz=_server_timezone()),
    )


@app.get(f"{settings.api_prefix}/market/mt4/specs", response_model=list[BrokerSymbolSpec])
def mt4_symbol_specs() -> list[BrokerSymbolSpec]:
    specs = list_mt4_symbol_specs(_mt4_files_dir())
    return [specs[key] for key in sorted(specs)]


@app.get(
    f"{settings.api_prefix}/shadow/blocked-probes",
    response_model=list[BlockedProbeRuntime],
)
def blocked_probe_overview() -> list[BlockedProbeRuntime]:
    return load_blocked_probe_registry(settings.shadow_ledger_dir)


@app.get(
    f"{settings.api_prefix}/shadow/overview",
    response_model=list[ShadowOpportunityDiagnostic],
)
def shadow_overview() -> list[ShadowOpportunityDiagnostic]:
    return load_shadow_overview(
        settings.shadow_ledger_dir,
        symbols=settings.session_watch_symbols,
    )


@app.get(
    f"{settings.api_prefix}/shadow/mt4/btc/break-retest",
    response_model=ShadowOpportunityDiagnostic,
)
def btc_break_retest_shadow() -> ShadowOpportunityDiagnostic:
    files_dir = _mt4_files_dir()
    spec = get_mt4_symbol_spec(files_dir, "BTCUSD")
    if spec is None:
        raise HTTPException(status_code=404, detail="BTCUSD broker symbol spec not found")

    m5_path = files_dir / "mt4_bars_BTCUSD_M5.json"
    m15_path = files_dir / "mt4_bars_BTCUSD_M15.json"
    if not m5_path.is_file() or not m15_path.is_file():
        raise HTTPException(status_code=404, detail="BTCUSD closed-bar snapshots not found")

    try:
        bars_m5 = read_closed_bar_snapshot(m5_path, "BTCUSD", Timeframe.M5)
        bars_m15 = read_closed_bar_snapshot(m15_path, "BTCUSD", Timeframe.M15)
        return scan_btc_break_retest_shadow(
            bars_m5,
            bars_m15,
            spec,
            datetime.now(tz=_server_timezone()),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    f"{settings.api_prefix}/shadow/mt4/btc/break-retest/paper",
    response_model=ShadowPaperSummary,
)
def btc_break_retest_paper_summary() -> ShadowPaperSummary:
    state_path = settings.shadow_ledger_dir / "BTCUSD_break_retest_paper_state.json"
    trades_path = settings.shadow_ledger_dir / "BTCUSD_break_retest_paper_trades.jsonl"
    return load_shadow_paper_summary(
        state_path,
        trades_path,
        evidence_cutover_at=settings.paper_evidence_cutover_at,
    )


@app.post(
    f"{settings.api_prefix}/shadow/mt4/btc/break-retest/collect",
    response_model=ShadowCollectionResult,
)
def collect_btc_break_retest_shadow() -> ShadowCollectionResult:
    ledger_path = settings.shadow_ledger_dir / "BTCUSD_break_retest.jsonl"
    try:
        return collect_btc_break_retest_once(
            _mt4_files_dir(),
            ledger_path,
            datetime.now(tz=_server_timezone()),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    f"{settings.api_prefix}/research/mt4/backtest",
    response_model=OpportunityBacktestResult,
)
def mt4_opportunity_backtest(
    request: Mt4OpportunityBacktestRequest,
) -> OpportunityBacktestResult:
    files_dir = _mt4_files_dir()
    symbol = _normalized_symbol(request.symbol)
    spec = get_mt4_symbol_spec(files_dir, symbol)
    if spec is None:
        raise HTTPException(status_code=404, detail="MT4 broker symbol spec not found")

    m5_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M5)
    m15_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M15)
    if m5_path is None or m15_path is None:
        raise HTTPException(status_code=404, detail="M5/M15 MT4 history not found")

    bars_m5 = read_mt4_csv(m5_path, symbol, Timeframe.M5)
    bars_m15 = read_mt4_csv(m15_path, symbol, Timeframe.M15)
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=request.mechanism,
        split=request.split,
        requested_risk_fraction=request.requested_risk_fraction,
        slippage_spread_fraction=request.slippage_spread_fraction,
        macro_events=load_macro_events(settings.macro_events_path),
    )
    try:
        return run_opportunity_backtest(bars_m5, bars_m15, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    f"{settings.api_prefix}/research/mt4/matrix",
    response_model=PortfolioResearchResult,
)
def mt4_portfolio_research(
    request: PortfolioResearchRequest,
) -> PortfolioResearchResult:
    try:
        result = run_mt4_portfolio_research(
            _mt4_files_dir(),
            request,
            macro_events_path=settings.macro_events_path,
        )
        save_research_admissions(
            settings.shadow_ledger_dir / "strategy_admissions.json",
            result,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(f"{settings.api_prefix}/research/regime", response_model=RegimeSnapshot)
def research_regime(bars: list[MarketBar]) -> RegimeSnapshot:
    if not bars:
        raise HTTPException(status_code=422, detail="bars are required")
    if any(bar.timeframe != Timeframe.M15 for bar in bars):
        raise HTTPException(status_code=422, detail="regime engine requires M15 bars")
    if len({bar.symbol.upper() for bar in bars}) != 1:
        raise HTTPException(status_code=422, detail="regime bars must belong to one symbol")
    if any(
        current.timestamp <= previous.timestamp
        for previous, current in pairwise(bars)
    ):
        raise HTTPException(status_code=422, detail="regime bars must be chronological")
    return classify_regime(bars)


@app.post(f"{settings.api_prefix}/research/admission", response_model=AdmissionDecision)
def research_admission(evidence: StrategyEvidence) -> AdmissionDecision:
    return assess_strategy(evidence)


@app.get(
    f"{settings.api_prefix}/execution/demo/status",
    response_model=DemoExecutionStatus,
)
def demo_execution_status() -> DemoExecutionStatus:
    now = datetime.now(tz=_server_timezone())
    overview = build_trading_overview(
        _mt4_files_dir(),
        settings.shadow_ledger_dir,
        now,
    )
    macro = macro_gate_status(settings.macro_events_path, now)
    return build_demo_status(
        files_dir=_mt4_files_dir(),
        overview=overview,
        macro=macro,
        now=now,
    )


@app.post(
    f"{settings.api_prefix}/execution/demo/submit-selected/{{proposal_id}}",
    response_model=DemoOrderCommand,
)
def submit_selected_demo_execution(proposal_id: str) -> DemoOrderCommand:
    proposal = approval_gate.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")

    now = datetime.now(tz=_server_timezone())
    overview = build_trading_overview(
        _mt4_files_dir(),
        settings.shadow_ledger_dir,
        now,
    )
    macro = macro_gate_status(settings.macro_events_path, now)
    try:
        return submit_selected_demo_order(
            files_dir=_mt4_files_dir(),
            overview=overview,
            macro=macro,
            proposal=proposal,
            now=now,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(f"{settings.api_prefix}/execution/proposals", response_model=ExecutionProposal)
def create_execution_proposal(request: ExecutionProposalRequest) -> ExecutionProposal:
    return approval_gate.create(request)


@app.post(
    f"{settings.api_prefix}/execution/proposals/{{proposal_id}}/approve",
    response_model=ExecutionProposal,
)
def approve_execution_proposal(proposal_id: str) -> ExecutionProposal:
    try:
        return approval_gate.approve(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    f"{settings.api_prefix}/execution/proposals/{{proposal_id}}/decline",
    response_model=ExecutionProposal,
)
def decline_execution_proposal(proposal_id: str) -> ExecutionProposal:
    try:
        return approval_gate.decline(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(f"{settings.api_prefix}/market/bars", status_code=201)
def ingest_bar(bar: MarketBar) -> dict[str, object]:
    if bar.timeframe.value not in settings.allowed_timeframes:
        raise HTTPException(status_code=422, detail="timeframe not allowed")
    try:
        market_store.append(bar)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "accepted": True,
        "symbol": bar.symbol.upper(),
        "timeframe": bar.timeframe,
        "count": market_store.count(bar.symbol, bar.timeframe),
    }


@app.get(f"{settings.api_prefix}/market/{{symbol}}/{{timeframe}}/latest")
def latest_bar(symbol: str, timeframe: Timeframe) -> MarketBar:
    bar = market_store.latest(symbol, timeframe)
    if bar is None:
        raise HTTPException(status_code=404, detail="no market data for stream")
    return bar


@app.get(f"{settings.api_prefix}/market/mt4/{{symbol}}/{{timeframe}}/summary")
def mt4_history_summary(symbol: str, timeframe: Timeframe) -> dict[str, object]:
    files_dir = _mt4_files_dir()
    normalized_symbol = _normalized_symbol(symbol)
    path = resolve_mt4_history_path(files_dir, normalized_symbol, timeframe)
    if path is None:
        raise HTTPException(status_code=404, detail="MT4 history file not found")
    return summarize_mt4_csv(path, normalized_symbol, timeframe)
