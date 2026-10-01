from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.admission import AdmissionState
from app.domain.opportunity import OpportunityMechanism, PerformanceSummary, ResearchSplit


class ExecutionCostStressScenario(BaseModel):
    scenario_id: str
    spread_multiplier: float = Field(ge=1)
    slippage_spread_fraction: float = Field(ge=0, le=3)


class ExecutionCostStressRow(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    scenario: ExecutionCostStressScenario
    validation: PerformanceSummary
    holdout: PerformanceSummary
    admission_state: AdmissionState
    edge_survives: bool
    validation_expectancy_delta_vs_observed: float = 0.0
    holdout_expectancy_delta_vs_observed: float = 0.0


class ExecutionCostStressReport(BaseModel):
    generated_at: datetime
    capital_eur: float = Field(gt=0)
    capital_source: str
    split: ResearchSplit
    rows: list[ExecutionCostStressRow]
    broker_authority: bool = False
    limitations: list[str] = Field(default_factory=list)
