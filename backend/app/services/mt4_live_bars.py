import json
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import _server_timezone, mt4_epoch_to_server_datetime


def read_closed_bar_snapshot(
    path: Path,
    expected_symbol: str,
    expected_timeframe: Timeframe,
) -> list[MarketBar]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    symbol = str(payload.get("symbol", "")).upper()
    timeframe = str(payload.get("timeframe", ""))
    first_shift = int(payload.get("first_shift", 0))

    if symbol != expected_symbol.upper():
        raise ValueError("MT4 bar snapshot symbol mismatch")
    if timeframe != expected_timeframe.value:
        raise ValueError("MT4 bar snapshot timeframe mismatch")
    if first_shift != 1:
        raise ValueError("MT4 bar snapshot must contain closed bars only")

    raw_bars = payload.get("bars")
    if not isinstance(raw_bars, dict):
        raise TypeError("MT4 bar snapshot bars must be an object")

    timezone = _server_timezone()
    by_timestamp = {}
    for raw in raw_bars.values():
        try:
            timestamp = mt4_epoch_to_server_datetime(
                int(raw["timestamp"]),
                timezone,
            )
            bar = MarketBar(
                symbol=symbol,
                timeframe=expected_timeframe,
                timestamp=timestamp,
                open=float(raw["open"]),
                high=float(raw["high"]),
                low=float(raw["low"]),
                close=float(raw["close"]),
                volume=float(raw.get("volume", 0)),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        by_timestamp[timestamp] = bar

    bars = [by_timestamp[key] for key in sorted(by_timestamp)]
    if not bars:
        raise ValueError("MT4 bar snapshot contains no valid closed bars")
    return bars
