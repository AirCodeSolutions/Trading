from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.trading_intelligence import OpportunityCausalPattern


class DirectionalConsistency(StrEnum):
    ALIGNED_STABLE = "aligned_stable"
    OPPOSED_STABLE = "opposed_stable"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


class CausalEconomicCell(BaseModel):
    symbol: str
    pattern: OpportunityCausalPattern
    directional_consistency: DirectionalConsistency
    train_alignment_rate: float | None = Field(default=None, ge=0, le=1)
    validation_alignment_rate: float | None = Field(default=None, ge=0, le=1)
    holdout_alignment_rate: float | None = Field(default=None, ge=0, le=1)
    train_directional_episodes: int = Field(ge=0)
    validation_directional_episodes: int = Field(ge=0)
    holdout_directional_episodes: int = Field(ge=0)
    asset_feasible_stop_interval: bool
    best_stop_atr_multiple: float | None = Field(default=None, gt=0)
    best_approval_rate: float = Field(ge=0, le=1)
    minimum_reference_capital_eur: float = Field(ge=0)


class CausalEconomicMatrixReport(BaseModel):
    generated_at: datetime
    reference_capital_eur: float = Field(gt=0)
    cells: list[CausalEconomicCell] = Field(default_factory=list)
