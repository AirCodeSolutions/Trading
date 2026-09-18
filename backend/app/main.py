from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.domain.market import MarketBar, Timeframe
from app.services.market_store import MarketStore

app = FastAPI(title=settings.app_name, version="0.1.0")
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
    }


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
