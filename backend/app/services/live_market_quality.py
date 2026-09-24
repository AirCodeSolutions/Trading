from datetime import datetime
from pathlib import Path

from app.domain.broker import MarketQualityRequest, MarketQualityResult
from app.domain.market import Timeframe
from app.services.market_quality import assess_market
from app.services.mt4_market_data import load_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.opportunity_strategies import _atr_series
from app.services.runtime_capital import resolve_demo_sizing_capital


def build_live_market_quality(
    files_dir: Path,
    now: datetime,
    symbols: tuple[str, ...],
) -> list[MarketQualityResult]:
    rows: list[MarketQualityResult] = []
    runtime_capital = resolve_demo_sizing_capital(files_dir)
    capital_eur = runtime_capital.capital_eur

    for symbol in symbols:
        normalized = symbol.upper()
        spec = get_mt4_symbol_spec(files_dir, normalized)
        if spec is None:
            continue

        bars_m5 = load_closed_market_bars(
            files_dir,
            normalized,
            Timeframe.M5,
            now,
        )
        bars_m15 = load_closed_market_bars(
            files_dir,
            normalized,
            Timeframe.M15,
            now,
        )
        if not bars_m5 or not bars_m15:
            continue

        atr_m5 = _atr_series(bars_m5)[-1]
        atr_m15 = _atr_series(bars_m15)[-1]
        if atr_m5 <= 0 or atr_m15 <= 0:
            continue

        rows.append(
            assess_market(
                MarketQualityRequest(
                    spec=spec,
                    atr_m5=atr_m5,
                    atr_m15=atr_m15,
                    capital_eur=capital_eur,
                )
            )
        )

    rows.sort(
        key=lambda row: (
            not row.eligible_for_m15_research,
            -row.execution_quality_score,
            row.symbol,
        )
    )
    return rows
