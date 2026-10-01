from datetime import datetime
from pathlib import Path

from app.domain.market import Timeframe
from app.domain.position_manager import PositionManagerReport
from app.services.mt4_market_data import load_closed_market_bars
from app.services.position_manager_v2 import build_position_manager_report
from app.services.shadow_paper import load_closed_trades


def build_runtime_position_manager_report(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int,
) -> PositionManagerReport:
    trades = []
    for trades_path in runtime_dir.glob("*_paper_trades.jsonl"):
        trades.extend(load_closed_trades(trades_path))

    symbols = sorted({trade.symbol for trade in trades})
    bars_by_symbol = {
        symbol: load_closed_market_bars(files_dir, symbol, Timeframe.M5, now)
        for symbol in symbols
    }
    bars_by_symbol_m15 = {
        symbol: load_closed_market_bars(files_dir, symbol, Timeframe.M15, now)
        for symbol in symbols
    }
    return build_position_manager_report(
        trades,
        bars_by_symbol,
        bars_by_symbol_m15=bars_by_symbol_m15,
        now=now,
        window_hours=window_hours,
    )
