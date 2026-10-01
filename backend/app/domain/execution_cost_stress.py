from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CostStressScenario(StrEnum):
    OBSERVED = "observed"
    ADVERSE_25 = "adverse_25"
    ADVERSE_50 = "adverse_50"


class CostStressWindowMetrics(BaseModel):
    trades: int = Field(ge=0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)
    average_execution_cost_r: float = Field(ge=0)


class CostStressScenarioResult(BaseModel):
    scenario: CostStressScenario
    spread_multiplier: float = Field(gt=0)
    slippage_spread_fraction: float = Field(ge=0)
    effective_spread: float = Field(gt=0)
    validation: CostStressWindowMetrics
    holdout: CostStressWindowMetrics
    weakest_expectancy_r: float
    weakest_profit_factor: float
    worst_drawdown_r: float
    positive_both_windows: bool
    authority_effect: bool = False


class ExecutionCostStressReport(BaseModel):
    generated_at: datetime
    symbol: str
    strategy_id: str
    target_r: float
    capital_eur: float
    capital_source: str
    baseline_spread: float = Field(gt=0)
    scenarios: list[CostStressScenarioResult]
    all_scenarios_positive_both_windows: bool
    authority_effect: bool = False
    limitations: list[str] = Field(default_factory=list)
