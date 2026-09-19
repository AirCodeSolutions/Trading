import csv
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.domain.market import MarketBar, Timeframe


def _server_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.mt4_server_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"unknown MT4 server timezone: {settings.mt4_server_timezone}"
        ) from exc


def _parse_bar_row(
    row: list[str],
    *,
    symbol: str,
    timeframe: Timeframe,
    server_timezone: ZoneInfo,
) -> MarketBar | None:
    if not row:
        return None

    first = row[0].strip().lower()
    if first in {"date", "timestamp"}:
        return None

    try:
        if len(row) >= 7:
            timestamp = datetime.strptime(
                f"{row[0].strip()} {row[1].strip()}",
                "%Y%m%d %H:%M:%S",
            ).replace(tzinfo=server_timezone)
            values = row[2:7]
        elif len(row) >= 6:
            unix_timestamp = int(row[0].strip())
            timestamp = datetime.fromtimestamp(unix_timestamp, tz=UTC).astimezone(
                server_timezone
            )
            values = row[1:6]
        else:
            return None

        open_price, high, low, close, volume = (float(value) for value in values)
        return MarketBar(
            symbol=symbol.upper(),
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
    except (ValueError, TypeError, OverflowError):
        return None


def read_mt4_csv(path: Path, symbol: str, timeframe: Timeframe) -> list[MarketBar]:
    by_timestamp: dict[datetime, MarketBar] = {}
    server_timezone = _server_timezone()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            bar = _parse_bar_row(
                row,
                symbol=symbol,
                timeframe=timeframe,
                server_timezone=server_timezone,
            )
            if bar is not None:
                by_timestamp[bar.timestamp] = bar

    return [by_timestamp[key] for key in sorted(by_timestamp)]


def summarize_mt4_csv(path: Path, symbol: str, timeframe: Timeframe) -> dict[str, object]:
    bars = read_mt4_csv(path, symbol, timeframe)
    if not bars:
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "count": 0,
            "first_bar": None,
            "last_bar": None,
        }
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": len(bars),
        "first_bar": bars[0].timestamp,
        "last_bar": bars[-1].timestamp,
    }
