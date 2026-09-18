from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.domain.admission import AdmissionDecision, StrategyEvidence
from app.domain.approval import ExecutionProposal, ExecutionProposalRequest
from app.domain.broker import (
    MarketQualityRequest,
    MarketQualityResult,
    PositionSizeRequest,
    PositionSizeResult,
)
from app.domain.market import MarketBar, Timeframe
from app.domain.regime import RegimeSnapshot
from app.services.admission import assess_strategy
from app.services.approval_gate import ApprovalGate
from app.services.capital_risk import size_position
from app.services.market_quality import assess_market
from app.services.market_store import MarketStore
from app.services.mt4_csv import summarize_mt4_csv
from app.services.regime import classify_regime

app = FastAPI(title=settings.app_name, version="0.3.0")
market_store = MarketStore()
approval_gate = ApprovalGate(settings.decision_mode)


@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


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
        "max_spread_to_stop": settings.max_spread_to_stop,
    }


@app.post(f"{settings.api_prefix}/risk/size", response_model=PositionSizeResult)
def risk_size(request: PositionSizeRequest) -> PositionSizeResult:
    return size_position(request)


@app.post(f"{settings.api_prefix}/markets/quality", response_model=MarketQualityResult)
def market_quality(request: MarketQualityRequest) -> MarketQualityResult:
    return assess_market(request)


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
        for previous, current in zip(bars, bars[1:], strict=False)
    ):
        raise HTTPException(status_code=422, detail="regime bars must be chronological")
    return classify_regime(bars)


@app.post(f"{settings.api_prefix}/research/admission", response_model=AdmissionDecision)
def research_admission(evidence: StrategyEvidence) -> AdmissionDecision:
    return assess_strategy(evidence)


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
    if settings.mt4_files_dir is None:
        raise HTTPException(status_code=503, detail="MT4 files directory is not configured")

    normalized_symbol = symbol.upper()
    if not normalized_symbol.isalnum() or len(normalized_symbol) > 32:
        raise HTTPException(status_code=422, detail="invalid symbol")

    path = Path(settings.mt4_files_dir) / f"{normalized_symbol}-{timeframe.value}.csv"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="MT4 history file not found")

    return summarize_mt4_csv(path, normalized_symbol, timeframe)
