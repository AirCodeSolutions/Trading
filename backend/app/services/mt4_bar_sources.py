from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_live_bars import read_closed_bar_snapshot

_csv_cache: dict[tuple[Path, Timeframe], tuple[int, list[MarketBar]]] = {}


def load_freshest_closed_bars(
    files_dir: Path,
    symbol: str,
    timeframe: Timeframe,
    evaluated_at: datetime,
) -> list[MarketBar]:
    if evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    normalized = symbol.upper()
    duration = timedelta(minutes=5 if timeframe == Timeframe.M5 else 15)
    candidates: list[tuple[int, list[MarketBar]]] = []

    snapshot = files_dir / f"mt4_bars_{normalized}_{timeframe.value}.json"
    if snapshot.is_file():
        try:
            bars = read_closed_bar_snapshot(snapshot, normalized, timeframe)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            bars = []
        filtered = _closed_at(bars, evaluated_at, duration)
        if filtered:
            # Prefer the compact closed-bar snapshot only when timestamps tie.
            candidates.append((2, filtered))

    legacy = files_dir / f"{normalized}-{timeframe.value}.csv"
    if legacy.is_file():
        filtered = _closed_at(
            _cached_csv_bars(legacy, normalized, timeframe),
            evaluated_at,
            duration,
        )
        if filtered:
            candidates.append((1, filtered))

    research = files_dir / f"mt4_research_bars_{normalized}_{timeframe.value}.csv"
    if research.is_file():
        filtered = _closed_at(
            _cached_csv_bars(research, normalized, timeframe),
            evaluated_at,
            duration,
        )
        if filtered:
            candidates.append((0, filtered))

    if not candidates:
        return []

    _, bars = max(
        candidates,
        key=lambda item: (item[1][-1].timestamp, item[0]),
    )
    return bars


def _closed_at(
    bars: list[MarketBar],
    evaluated_at: datetime,
    duration: timedelta,
) -> list[MarketBar]:
    return [
        bar
        for bar in bars
        if bar.timestamp + duration <= evaluated_at
    ]


def _cached_csv_bars(
    path: Path,
    symbol: str,
    timeframe: Timeframe,
) -> list[MarketBar]:
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return []

    key = (path, timeframe)
    cached = _csv_cache.get(key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        bars = read_mt4_csv(path, symbol, timeframe)
    except (OSError, TypeError, ValueError):
        bars = []

    _csv_cache[key] = (mtime_ns, bars)
    return bars
