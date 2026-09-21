from pathlib import Path

from app.domain.admission import AdmissionState
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityBacktestResult,
    PortfolioResearchRequest,
    PortfolioResearchResult,
)
from app.services.macro_gate import load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import run_opportunity_backtest


def run_mt4_portfolio_research(
    files_dir: Path,
    request: PortfolioResearchRequest,
    *,
    macro_events_path: Path | None = None,
) -> PortfolioResearchResult:
    specs = list_mt4_symbol_specs(files_dir)
    macro_events = (
        load_macro_events(macro_events_path)
        if macro_events_path is not None
        else []
    )
    requested_symbols = (
        sorted(specs)
        if request.symbols is None
        else sorted({symbol.upper() for symbol in request.symbols})
    )

    results: list[OpportunityBacktestResult] = []
    skipped_symbols: dict[str, str] = {}

    for symbol in requested_symbols:
        if not symbol.isalnum() or len(symbol) > 32:
            skipped_symbols[symbol] = "invalid symbol"
            continue

        spec = specs.get(symbol)
        if spec is None:
            skipped_symbols[symbol] = "broker symbol spec not found"
            continue

        m5_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M5)
        m15_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M15)
        if m5_path is None or m15_path is None:
            skipped_symbols[symbol] = "M5/M15 history not found"
            continue

        bars_m5 = read_mt4_csv(m5_path, symbol, Timeframe.M5)
        bars_m15 = read_mt4_csv(m15_path, symbol, Timeframe.M15)
        if not bars_m5 or not bars_m15:
            skipped_symbols[symbol] = "M5/M15 history is empty"
            continue

        for mechanism in request.mechanisms:
            config = OpportunityBacktestConfig(
                spec=spec,
                mechanism=mechanism,
                split=request.split,
                requested_risk_fraction=request.requested_risk_fraction,
                slippage_spread_fraction=request.slippage_spread_fraction,
                macro_events=macro_events,
            )
            results.append(run_opportunity_backtest(bars_m5, bars_m15, config))

    results.sort(key=_research_sort_key, reverse=True)
    qualified = [
        result
        for result in results
        if result.admission.state == AdmissionState.ACTIVE
    ]

    if not qualified:
        qualified_strategy_id = None
        selection_reason = (
            "no market-mechanism pair is ACTIVE; research output cannot authorize execution"
        )
    else:
        winner = max(qualified, key=_robust_key)
        qualified_strategy_id = winner.admission.strategy_id
        selection_reason = (
            "qualified pair selected by weakest independent expectancy, "
            "then weakest profit factor and execution cost"
        )

    return PortfolioResearchResult(
        results=results,
        skipped_symbols=skipped_symbols,
        qualified_strategy_id=qualified_strategy_id,
        selection_reason=selection_reason,
    )


def _research_sort_key(result: OpportunityBacktestResult) -> tuple[float, float, float, float]:
    state_rank = {
        AdmissionState.ACTIVE: 2.0,
        AdmissionState.SHADOW: 1.0,
        AdmissionState.REJECTED: 0.0,
    }[result.admission.state]
    robust = _robust_key(result)
    return state_rank, *robust


def _robust_key(result: OpportunityBacktestResult) -> tuple[float, float, float]:
    weakest_expectancy = min(
        result.validation.expectancy_r,
        result.holdout.expectancy_r,
    )
    weakest_profit_factor = min(
        result.validation.profit_factor,
        result.holdout.profit_factor,
    )
    worst_cost = max(
        result.validation.average_execution_cost_r,
        result.holdout.average_execution_cost_r,
    )
    return weakest_expectancy, weakest_profit_factor, -worst_cost
