import csv
from datetime import datetime
from pathlib import Path

from app.domain.market import MarketBar, Timeframe


def read_mt4_csv(path: Path, symbol: str, timeframe: Timeframe) -> list[MarketBar]:
    by_timestamp: dict[datetime, MarketBar] = {}

    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or row[0].strip().lower() == "date":
                continue
            if len(row) < 7:
                continue
            try:
                timestamp = datetime.strptime(
                    f"{row[0].strip()} {row[1].strip()}",
                    "%Y%m%d %H:%M:%S",
                )
                bar = MarketBar(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(row[2]),
                    high=float(row[3]),
                    low=float(row[4]),
                    close=float(row[5]),
                    volume=float(row[6]),
                )
            except (ValueError, TypeError):
                continue
            by_timestamp[timestamp] = bar

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
