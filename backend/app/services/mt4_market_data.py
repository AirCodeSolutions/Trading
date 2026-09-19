from datetime import datetime, timedelta
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_live_bars import read_closed_bar_snapshot


def load_closed_market_bars(
    files_dir: Path,
    symbol: str,
    timeframe: Timeframe,
    evaluated_at: datetime,
) -> list[MarketBar]:
    snapshot = files_dir / f"mt4_bars_{symbol}_{timeframe.value}.json"
    bars: list[MarketBar] = []
    if snapshot.is_file():
        try:
            bars = read_closed_bar_snapshot(snapshot, symbol, timeframe)
        except (OSError, TypeError, ValueError):
            bars = []

    if not bars:
        path = resolve_mt4_history_path(files_dir, symbol, timeframe)
        if path is None:
            return []
        try:
            bars = read_mt4_csv(path, symbol, timeframe)
        except (OSError, TypeError, ValueError):
            return []

    duration = timedelta(minutes=5 if timeframe == Timeframe.M5 else 15)
    return [
        bar
        for bar in bars
        if bar.timestamp + duration <= evaluated_at
    ]
