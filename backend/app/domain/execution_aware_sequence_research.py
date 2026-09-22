from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.trading_intelligence import OpportunityCausalPattern


class ExecutionAwareConsistency(StrEnum):
    POSITIVE_STABLE = "positive_stable"
    NEGATIVE_STABLE = "negative_stable"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


class ExecutionAwareSplitSummary(BaseModel):
    occurrences: int = Field(ge=0)
    executed: int = Field(ge=0)
    rejected_macro: int = Field(ge=0)
    rejected_sizing: int = Field(ge=0)
    rejected_other: int = Field(ge=0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    max_drawdown_r: float = Field(ge=0)
    average_execution_cost_r: float = Field(ge=0)
    asset_baseline_expectancy_r: float
    expectancy_delta_vs_baseline_r: float


class ExecutionAwareSequenceSummary(BaseModel):
    sequence: list[OpportunityCausalPattern] = Field(min_length=1)
    consistency: ExecutionAwareConsistency
    stop_atr_multiple: float = Field(gt=0)
    target_r: float = Field(gt=0)
    train: ExecutionAwareSplitSummary
    validation: ExecutionAwareSplitSummary
    holdout: ExecutionAwareSplitSummary


class AssetExecutionAwareSequenceResearch(BaseModel):
    symbol: str
    feasible_stop_interval: bool
    stop_atr_multiple: float | None = Field(default=None, gt=0)
    baseline_train_expectancy_r: float
    baseline_validation_expectancy_r: float
    baseline_holdout_expectancy_r: float
    sequences: list[ExecutionAwareSequenceSummary] = Field(default_factory=list)


class ExecutionAwareSequenceResearchReport(BaseModel):
    generated_at: datetime
    train_end: datetime
    validation_end: datetime
    sequence_length: int = Field(ge=2, le=6)
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    reference_capital_eur: float = Field(gt=0)
    assets: list[AssetExecutionAwareSequenceResearch] = Field(default_factory=list)
