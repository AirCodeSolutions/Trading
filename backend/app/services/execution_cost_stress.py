from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.domain.execution_cost_stress import (
    CostStressScenario,
    CostStressScenarioResult,
    CostStressWindowMetrics,
    ExecutionCostStressReport,
)
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityMechanism,
    PerformanceSummary,
)
from app.services.macro_gate import load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.opportunity_backtester import run_opportunity_backtest
from app.services.probe_review import default_probe_review_split
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.runtime_capital import resolve_demo_sizing_capital


@dataclass(frozen=True)
class CostScenario:
    scenario: CostStressScenario
    spread_multiplier: float
    slippage_spread_fraction: float


SCENARIOS = (
    CostScenario(CostStressScenario.OBSERVED, 1.0, 0.25),
    CostScenario(CostStressScenario.ADVERSE_25, 1.25, 0.50),
    CostScenario(CostStressScenario.ADVERSE_50, 1.50, 1.00),
)


def _window(summary: PerformanceSummary) -> CostStressWindowMetrics:
    return CostStressWindowMetrics(
        trades=summary.trades,
        total_r=summary.total_r,
        expectancy_r=summary.expectancy_r,
        profit_factor=summary.profit_factor,
        max_drawdown_r=summary.max_drawdown_r,
        average_execution_cost_r=summary.average_execution_cost_r,
    )


def build_xau_structural_displacement_cost_stress(
    files_dir: Path,
    *,
    generated_at: datetime,
    risk_fraction: float,
    research_execution_model_path: Path,
    macro_events_path: Path,
) -> ExecutionCostStressReport:
    symbol = "XAUUSD"
    mechanism = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE

    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or capital.capital_eur <= 0:
        raise ValueError("MT4 DEMO sizing capital is unavailable")

    spec = get_mt4_symbol_spec(files_dir, symbol)
    if spec is None:
        raise ValueError("XAUUSD broker symbol spec is unavailable")

    execution_model = load_research_execution_model(
        research_execution_model_path
    )
    if execution_model is not None:
        spec = apply_research_execution_model(spec, execution_model)

    bars_m5 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    bars_m15 = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M15),
        symbol,
        Timeframe.M15,
    )
    if not bars_m5 or not bars_m15:
        raise ValueError("XAUUSD M5 and M15 histories are required")

    split = default_probe_review_split()
    macro_events = load_macro_events(macro_events_path)
    baseline_spread = spec.spread
    results: list[CostStressScenarioResult] = []

    for scenario in SCENARIOS:
        stressed_spec = spec.model_copy(
            update={"ask": spec.bid + baseline_spread * scenario.spread_multiplier}
        )
        backtest = run_opportunity_backtest(
            bars_m5,
            bars_m15,
            OpportunityBacktestConfig(
                spec=stressed_spec,
                mechanism=mechanism,
                split=split,
                requested_risk_fraction=risk_fraction,
                capital_eur=capital.capital_eur,
                slippage_spread_fraction=scenario.slippage_spread_fraction,
                macro_events=macro_events,
            ),
        )
        validation = _window(backtest.validation)
        holdout = _window(backtest.holdout)
        results.append(
            CostStressScenarioResult(
                scenario=scenario.scenario,
                spread_multiplier=scenario.spread_multiplier,
                slippage_spread_fraction=scenario.slippage_spread_fraction,
                effective_spread=stressed_spec.spread,
                validation=validation,
                holdout=holdout,
                weakest_expectancy_r=min(
                    validation.expectancy_r,
                    holdout.expectancy_r,
                ),
                weakest_profit_factor=min(
                    validation.profit_factor,
                    holdout.profit_factor,
                ),
                worst_drawdown_r=max(
                    validation.max_drawdown_r,
                    holdout.max_drawdown_r,
                ),
                positive_both_windows=(
                    validation.trades > 0
                    and holdout.trades > 0
                    and validation.expectancy_r > 0
                    and holdout.expectancy_r > 0
                    and validation.profit_factor > 1
                    and holdout.profit_factor > 1
                ),
                authority_effect=False,
            )
        )

    return ExecutionCostStressReport(
        generated_at=generated_at,
        symbol=symbol,
        strategy_id=f"{symbol}:{mechanism.value}",
        target_r=1.5,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        baseline_spread=baseline_spread,
        scenarios=results,
        all_scenarios_positive_both_windows=all(
            row.positive_both_windows for row in results
        ),
        authority_effect=False,
        limitations=[
            "Stress changes spread and slippage assumptions only.",
            "Signal logic, structural stop, 1.5R target and 12-M5 horizon remain unchanged.",
            "This report is descriptive and cannot alter admission or broker authority.",
            "The backtest uses actual MT4 DEMO equity or balance via runtime capital resolution.",
        ],
    )
