from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.domain.broker import (
    MarketQualityRequest,
    MarketQualityResult,
    PositionSizeRequest,
    PositionSizeResult,
)
from app.domain.market import MarketBar, Timeframe
from app.services.capital_risk import size_position
from app.services.market_quality import assess_market
from app.services.market_store import MarketStore
from app.services.mt4_csv import summarize_mt4_csv

app = FastAPI(title=settings.app_name, version="0.2.0")
market_store = MarketStore()


@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get(f"{settings.api_prefix}/config")
def runtime_config() -> dict[str, object]:
    return {
        "execution_mode": settings.execution_mode,
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
