import csv
import json
from datetime import datetime
from pathlib import Path

from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import mt4_epoch_to_server_datetime, read_mt4_csv
from app.services.mt4_live_bars import read_closed_bar_snapshot

LIVE_MAX_AGE_SECONDS = 120
SPARKLINE_BARS = 48

_history_cache: dict[Path, tuple[int, list[MarketBar]]] = {}


def read_live_market_quotes(
    files_dir: Path,
    now: datetime,
    symbols: tuple[str, ...] | None = None,
) -> list[LiveMarketQuote]:
    allowed = {symbol.upper() for symbol in symbols} if symbols else None
    raw_quotes: dict[str, tuple[datetime, float, float, int]] = {}

    snapshot_path = files_dir / "trading_symbol_specs.csv"
    if snapshot_path.is_file():
        try:
            with snapshot_path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    parsed = _parse_csv_quote(row)
                    if parsed is not None and (
                        allowed is None or parsed[0] in allowed
                    ):
                        _keep_newest(raw_quotes, *parsed)
        except OSError:
            pass

    for path in sorted(files_dir.glob("mt4_data_*.json")):
        file_symbol = path.stem.removeprefix("mt4_data_").upper()
        if allowed is not None and file_symbol not in allowed:
            continue
        parsed = _parse_json_quote(path)
        if parsed is not None and (allowed is None or parsed[0] in allowed):
            _keep_newest(raw_quotes, *parsed)

    return [
        _build_quote(symbol, values, files_dir, now)
        for symbol, values in sorted(raw_quotes.items())
    ]


def _parse_csv_quote(
    row: dict[str, str | None],
) -> tuple[str, datetime, float, float, int] | None:
    try:
        symbol = str(row["symbol"]).strip().upper()
        timestamp = mt4_epoch_to_server_datetime(int(str(row["timestamp"])))
        bid = float(str(row["bid"]))
        ask = float(str(row["ask"]))
        digits = int(str(row["digits"]))
    except (KeyError, TypeError, ValueError):
        return None
    if not symbol or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return symbol, timestamp, bid, ask, digits


def _parse_json_quote(
    path: Path,
) -> tuple[str, datetime, float, float, int] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        symbol = str(payload["symbol"]).upper()
        timestamp = mt4_epoch_to_server_datetime(int(payload["timestamp"]))
        bid = float(payload["bid"])
        ask = float(payload["ask"])
        digits = int(payload["digits"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None
    if not symbol or bid <= 0 or ask <= 0 or ask < bid:
        return None
    return symbol, timestamp, bid, ask, digits


def _keep_newest(
    quotes: dict[str, tuple[datetime, float, float, int]],
    symbol: str,
    timestamp: datetime,
    bid: float,
    ask: float,
    digits: int,
) -> None:
    current = quotes.get(symbol)
    if current is None or timestamp >= current[0]:
        quotes[symbol] = (timestamp, bid, ask, digits)


def _build_quote(
    symbol: str,
    values: tuple[datetime, float, float, int],
    files_dir: Path,
    now: datetime,
) -> LiveMarketQuote:
    timestamp, bid, ask, digits = values
    age_seconds = max(0.0, (now - timestamp).total_seconds())
    status = (
        MarketFeedStatus.LIVE
        if age_seconds <= LIVE_MAX_AGE_SECONDS
        else MarketFeedStatus.STALE
    )
    mid = (bid + ask) / 2
    spread = ask - bid

    bars = _recent_m5_bars(files_dir, symbol)
    closes = [bar.close for bar in bars]
    last_closed_m5_at = bars[-1].timestamp if bars else None
    recent_change_pct = None
    if len(closes) >= 2 and closes[0] > 0:
        recent_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100

    return LiveMarketQuote(
        symbol=symbol,
        as_of=timestamp,
        bid=bid,
        ask=ask,
        mid=mid,
        spread=spread,
        spread_pct=(spread / mid) * 100,
        digits=digits,
        age_seconds=age_seconds,
        status=status,
        last_closed_m5_at=last_closed_m5_at,
        recent_change_pct=recent_change_pct,
        recent_m5_closes=closes,
    )


def _recent_m5_bars(files_dir: Path, symbol: str) -> list[MarketBar]:
    snapshot_path = files_dir / f"mt4_bars_{symbol}_M5.json"
    if snapshot_path.is_file():
        try:
            bars = read_closed_bar_snapshot(snapshot_path, symbol, Timeframe.M5)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            bars = []
        if bars:
            return bars[-SPARKLINE_BARS:]

    legacy_path = files_dir / f"{symbol}-M5.csv"
    if legacy_path.is_file():
        bars = _cached_history_tail(legacy_path, symbol)
        if bars:
            return bars

    research_path = files_dir / f"mt4_research_bars_{symbol}_M5.csv"
    if research_path.is_file():
        return _cached_history_tail(research_path, symbol)

    return []


def _cached_history_tail(path: Path, symbol: str) -> list[MarketBar]:
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return []

    cached = _history_cache.get(path)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        bars = read_mt4_csv(path, symbol, Timeframe.M5)[-SPARKLINE_BARS:]
    except (OSError, TypeError, ValueError):
        bars = []

    _history_cache[path] = (mtime_ns, bars)
    return bars
