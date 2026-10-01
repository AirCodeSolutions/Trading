from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.execution_cost_stress import (
    ExecutionCostStressReport,
    ExecutionCostStressRow,
    ExecutionCostStressScenario,
)
from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityBacktestConfig, OpportunityMechanism
from app.services.admission import MAX_DRAWDOWN_R, MIN_PROFIT_FACTOR
from app.services.macro_gate import load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import run_opportunity_backtest
from app.services.probe_review import default_probe_review_split
from app.services.research_execution_model import load_research_execution_model
from app.services.runtime_capital import resolve_demo_sizing_capital

REPORT_FILE = "execution_cost_stress.json"

SCENARIOS = (
    ExecutionCostStressScenario(
        scenario_id="observed",
        spread_multiplier=1.0,
        slippage_spread_fraction=0.25,
    ),
    ExecutionCostStressScenario(
        scenario_id="spread_1_25x",
        spread_multiplier=1.25,
        slippage_spread_fraction=0.25,
    ),
    ExecutionCostStressScenario(
        scenario_id="spread_1_50x",
        spread_multiplier=1.50,
        slippage_spread_fraction=0.25,
    ),
)

CANDIDATE_FAMILIES = (
    ("XAUUSD", OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE),
    ("XAUUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE),
)


def _stressed_spec(
    spec: BrokerSymbolSpec,
    observed_spread: float,
    multiplier: float,
) -> BrokerSymbolSpec:
    return spec.model_copy(
        update={"ask": spec.bid + observed_spread * multiplier}
    )
def _edge_survives(result) -> bool:
    return (
        result.validation.expectancy_r > 0
        and result.holdout.expectancy_r > 0
        and result.validation.profit_factor >= MIN_PROFIT_FACTOR
        and result.holdout.profit_factor >= MIN_PROFIT_FACTOR
        and max(
            result.validation.max_drawdown_r,
            result.holdout.max_drawdown_r,
        )
        <= MAX_DRAWDOWN_R
    )


def evaluate_execution_cost_stress(
    files_dir: Path,
    *,
    generated_at: datetime,
) -> ExecutionCostStressReport:
    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None:
        raise ValueError("MT4 DEMO sizing capital is unavailable")

    execution_model = load_research_execution_model(
        settings.research_execution_model_path
    )
    specs = list_mt4_symbol_specs(files_dir)
    macro_events = load_macro_events(settings.macro_events_path)
    split = default_probe_review_split()
    rows: list[ExecutionCostStressRow] = []

    for symbol, mechanism in CANDIDATE_FAMILIES:
        raw_spec = specs.get(symbol)
        if raw_spec is None:
            raise ValueError(f"broker symbol spec missing for {symbol}")
        proxy = execution_model.symbols.get(symbol)
        if proxy is None:
            raise ValueError(f"research spread proxy missing for {symbol}")
        m5_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M5)
        m15_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M15)
        if m5_path is None or m15_path is None:
            raise ValueError(f"M5/M15 history missing for {symbol}")
        bars_m5 = read_mt4_csv(m5_path, symbol, Timeframe.M5)
        bars_m15 = read_mt4_csv(m15_path, symbol, Timeframe.M15)

        baseline = None
        family_rows = []
        for scenario in SCENARIOS:
            config = OpportunityBacktestConfig(
                spec=_stressed_spec(
                    raw_spec,
                    proxy.spread,
                    scenario.spread_multiplier,
                ),
                mechanism=mechanism,
                split=split,
                requested_risk_fraction=settings.risk_per_trade_fraction,
                capital_eur=capital.capital_eur,
                slippage_spread_fraction=scenario.slippage_spread_fraction,
                macro_events=macro_events,
            )
            result = run_opportunity_backtest(bars_m5, bars_m15, config)
            if baseline is None:
                baseline = result
            family_rows.append((scenario, result))

        assert baseline is not None
        for scenario, result in family_rows:
            rows.append(
                ExecutionCostStressRow(
                    strategy_id=f"{symbol}:{mechanism.value}",
                    symbol=symbol,
                    mechanism=mechanism,
                    scenario=scenario,
                    validation=result.validation,
                    holdout=result.holdout,
                    admission_state=result.admission.state,
                    edge_survives=_edge_survives(result),
                    validation_expectancy_delta_vs_observed=(
                        result.validation.expectancy_r
                        - baseline.validation.expectancy_r
                    ),
                    holdout_expectancy_delta_vs_observed=(
                        result.holdout.expectancy_r
                        - baseline.holdout.expectancy_r
                    ),
                )
            )
    return ExecutionCostStressReport(
        generated_at=generated_at,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        split=split,
        rows=rows,
        broker_authority=False,
        limitations=[
            "research-only stress; no runtime quote or spread guard is modified",
            "scenarios stress spread proxy only; slippage remains a fixed fraction of spread",
            "candidate families are preregistered XAU structural displacement and persistence",
        ],
    )


def save_execution_cost_stress_report(
    path: Path,
    report: ExecutionCostStressReport,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def load_execution_cost_stress_report(
    path: Path,
) -> ExecutionCostStressReport | None:
    if not path.is_file():
        return None
    try:
        return ExecutionCostStressReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
