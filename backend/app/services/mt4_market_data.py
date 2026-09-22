from datetime import datetime
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_bar_sources import load_freshest_closed_bars


def load_closed_market_bars(
    files_dir: Path,
    symbol: str,
    timeframe: Timeframe,
    evaluated_at: datetime,
) -> list[MarketBar]:
    return load_freshest_closed_bars(
        files_dir,
        symbol,
        timeframe,
        evaluated_at,
    )
