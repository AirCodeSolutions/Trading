import json
from datetime import datetime
from pathlib import Path

from app.domain.market import Timeframe
from app.domain.portfolio import MarketPriceSource, MarketUniverseAsset
from app.services.mt4_csv import mt4_epoch_to_server_datetime, read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_live_quotes import LIVE_MAX_AGE_SECONDS
from app.services.mt4_specs import list_mt4_symbol_specs


def build_market_universe(
    files_dir: Path,
    now: datetime,
) -> list[MarketUniverseAsset]:
    symbols = _discover_symbols(files_dir)
    specs = list_mt4_symbol_specs(files_dir)
    assets: list[MarketUniverseAsset] = []

    for symbol in sorted(symbols):
        quote = _read_quote(files_dir / f"mt4_data_{symbol}.json", now)
        m5_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M5)
        m15_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M15)
        has_m5 = m5_path is not None
        has_m15 = m15_path is not None
        spec_ready = symbol in specs

        if quote is not None:
            price = quote["mid"]
            as_of = quote["as_of"]
            source = MarketPriceSource.BROKER_QUOTE
            bid = quote["bid"]
            ask = quote["ask"]
            spread = ask - bid
            quote_live = quote["age_seconds"] <= LIVE_MAX_AGE_SECONDS
        else:
            bar = _last_bar(m5_path, symbol) if m5_path is not None else None
            if bar is None:
                continue
            price = bar.close
            as_of = bar.timestamp
            source = MarketPriceSource.CLOSED_M5
            bid = None
            ask = None
            spread = None
            quote_live = False

        research_ready = has_m5 and has_m15
        paper_ready = research_ready and spec_ready and quote is not None and quote_live
        reason = _reason(
            research_ready=research_ready,
            spec_ready=spec_ready,
            quote_available=quote is not None,
            quote_live=quote_live,
        )
        assets.append(
            MarketUniverseAsset(
                symbol=symbol,
                price=price,
                price_source=source,
                as_of=as_of,
                bid=bid,
                ask=ask,
                spread=spread,
                quote_live=quote_live,
                has_m5=has_m5,
                has_m15=has_m15,
                broker_spec_ready=spec_ready,
                research_ready=research_ready,
                paper_ready=paper_ready,
                reason=reason,
            )
        )

    return assets


def _discover_symbols(files_dir: Path) -> set[str]:
    symbols: set[str] = set()
    for path in files_dir.glob("*-M5.csv"):
        symbols.add(path.name.removesuffix("-M5.csv"))
    for path in files_dir.glob("mt4_research_bars_*_M5.csv"):
        name = path.name.removeprefix("mt4_research_bars_")
        symbols.add(name.removesuffix("_M5.csv"))
    for path in files_dir.glob("mt4_data_*.json"):
        symbols.add(path.stem.removeprefix("mt4_data_"))
    return {symbol for symbol in symbols if symbol}


def _read_quote(path: Path, now: datetime) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        bid = float(payload["bid"])
        ask = float(payload["ask"])
        as_of = mt4_epoch_to_server_datetime(int(payload["timestamp"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if bid <= 0 or ask < bid:
        return None
    return {
        "bid": bid,
        "ask": ask,
        "mid": (bid + ask) / 2,
        "as_of": as_of,
        "age_seconds": max(0.0, (now - as_of).total_seconds()),
    }


def _last_bar(path: Path, symbol: str):
    try:
        bars = read_mt4_csv(path, symbol, Timeframe.M5)
    except (OSError, TypeError, ValueError):
        return None
    return bars[-1] if bars else None


def _reason(
    *,
    research_ready: bool,
    spec_ready: bool,
    quote_available: bool,
    quote_live: bool,
) -> str:
    if not research_ready:
        return "M5/M15 history incomplete"
    if not spec_ready:
        return "research ready; broker symbol specification missing"
    if not quote_available:
        return "research/spec ready; broker quote bridge missing"
    if not quote_live:
        return "research/spec ready; latest broker quote is stale"
    return "research, broker spec and live quote ready"
