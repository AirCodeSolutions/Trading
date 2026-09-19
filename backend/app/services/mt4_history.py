from pathlib import Path

from app.domain.market import Timeframe


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
