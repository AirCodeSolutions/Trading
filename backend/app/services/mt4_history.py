from datetime import timedelta
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import read_mt4_csv


def resolve_mt4_history_path(
    files_dir: Path,
    symbol: str,
    timeframe: Timeframe,
) -> Path | None:
    normalized = symbol.upper()
    preferred = files_dir / f"mt4_research_bars_{normalized}_{timeframe.value}.csv"
    if preferred.is_file():
        return preferred

    fallback = files_dir / f"{normalized}-{timeframe.value}.csv"
    if fallback.is_file():
        return fallback
    return None


def load_mt4_research_history(
    files_dir: Path,
    symbol: str,
) -> tuple[list[MarketBar], list[MarketBar]]:
    normalized = symbol.upper()
    m5_path = resolve_mt4_history_path(files_dir, normalized, Timeframe.M5)
    m15_path = resolve_mt4_history_path(files_dir, normalized, Timeframe.M15)
    if m5_path is None or m15_path is None:
        raise FileNotFoundError(f"M5/M15 history not found for {normalized}")

    bars_m5 = read_mt4_csv(m5_path, normalized, Timeframe.M5)
    bars_m15_native = read_mt4_csv(m15_path, normalized, Timeframe.M15)
    if not bars_m5 or not bars_m15_native:
        return bars_m5, bars_m15_native

    return bars_m5, backfill_m15_prefix_from_m5(bars_m5, bars_m15_native)


def backfill_m15_prefix_from_m5(
    bars_m5: list[MarketBar],
    bars_m15_native: list[MarketBar],
) -> list[MarketBar]:
    if not bars_m5 or not bars_m15_native:
        return list(bars_m15_native)

    first_native_at = bars_m15_native[0].timestamp
    if bars_m5[0].timestamp >= first_native_at:
        return list(bars_m15_native)

    by_timestamp = {bar.timestamp: bar for bar in bars_m5}
    prefix: list[MarketBar] = []

    for first in bars_m5:
        timestamp = first.timestamp
        if timestamp >= first_native_at:
            break
        if timestamp.minute % 15 != 0:
            continue

        second = by_timestamp.get(timestamp + timedelta(minutes=5))
        third = by_timestamp.get(timestamp + timedelta(minutes=10))
        if second is None or third is None:
            continue
        if third.timestamp >= first_native_at:
            continue

        prefix.append(
            MarketBar(
                symbol=first.symbol,
                timeframe=Timeframe.M15,
                timestamp=timestamp,
                open=first.open,
                high=max(first.high, second.high, third.high),
                low=min(first.low, second.low, third.low),
                close=third.close,
                volume=first.volume + second.volume + third.volume,
            )
        )

    return [*prefix, *bars_m15_native]
