from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.causal_economic_matrix import DirectionalConsistency
from app.domain.trading_intelligence import OpportunityCausalPattern


class PredictiveLiftConsistency(StrEnum):
    ABOVE_BASELINE_STABLE = "above_baseline_stable"
    BELOW_BASELINE_STABLE = "below_baseline_stable"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


class CausalSequenceSplitSummary(BaseModel):
    episodes: int = Field(ge=0)
    directional_episodes: int = Field(ge=0)
    aligned: int = Field(ge=0)
    opposed: int = Field(ge=0)
    no_direction: int = Field(ge=0)
    alignment_rate: float | None = Field(default=None, ge=0, le=1)
    average_move_atr: float = Field(ge=0)
    occurrences: int = Field(default=0, ge=0)
    directional_occurrences: int = Field(default=0, ge=0)
    directional_successes: int = Field(default=0, ge=0)
    directional_success_rate: float | None = Field(default=None, ge=0, le=1)
    asset_baseline_success_rate: float | None = Field(default=None, ge=0, le=1)
    lift_vs_baseline: float | None = Field(default=None, ge=0)
    first_touch_occurrences: int = Field(default=0, ge=0)
    first_touch_successes: int = Field(default=0, ge=0)
    first_touch_success_rate: float | None = Field(default=None, ge=0, le=1)
    asset_baseline_first_touch_success_rate: float | None = Field(
        default=None, ge=0, le=1
    )
    first_touch_lift_vs_baseline: float | None = Field(default=None, ge=0)


class CausalSequenceHistoricalSummary(BaseModel):
    sequence: list[OpportunityCausalPattern] = Field(min_length=1)
    directional_consistency: DirectionalConsistency
    predictive_lift_consistency: PredictiveLiftConsistency
    first_touch_lift_consistency: PredictiveLiftConsistency
    train: CausalSequenceSplitSummary
    validation: CausalSequenceSplitSummary
    holdout: CausalSequenceSplitSummary


class AssetCausalSequenceResearch(BaseModel):
    symbol: str
    total_episodes: int = Field(ge=0)
    sequences: list[CausalSequenceHistoricalSummary] = Field(default_factory=list)


class CausalSequenceResearchReport(BaseModel):
    generated_at: datetime
    train_end: datetime
    validation_end: datetime
    move_threshold_atr: float = Field(gt=0)
    horizon_bars: int = Field(gt=0)
    sequence_length: int = Field(ge=2, le=6)
    assets: list[AssetCausalSequenceResearch] = Field(default_factory=list)
