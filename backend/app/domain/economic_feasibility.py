from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading_intelligence import OpportunityCausalPattern


class StopFeasibilitySummary(BaseModel):
    stop_atr_multiple: float = Field(gt=0)
    episodes: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected_spread: int = Field(ge=0)
    rejected_min_lot: int = Field(ge=0)
    rejected_margin: int = Field(ge=0)
    rejected_other: int = Field(ge=0)
    approval_rate: float = Field(ge=0, le=1)
    average_expected_loss_eur: float = Field(ge=0)
    average_lots: float = Field(ge=0)


class CausalPatternEconomicFeasibility(BaseModel):
    pattern: OpportunityCausalPattern
    stop_profiles: list[StopFeasibilitySummary] = Field(default_factory=list)


class AssetEconomicFeasibility(BaseModel):
    symbol: str
    frozen_spread: float = Field(gt=0)
    min_lot: float = Field(gt=0)
    min_lot_margin_eur: float = Field(ge=0)
    spread_stop_floor_price: float = Field(gt=0)
    risk_stop_ceiling_price: float = Field(gt=0)
    feasible_stop_interval: bool
    minimum_reference_capital_eur: float = Field(ge=0)
    total_episodes: int = Field(ge=0)
    stop_profiles: list[StopFeasibilitySummary] = Field(default_factory=list)
    causal_patterns: list[CausalPatternEconomicFeasibility] = Field(
        default_factory=list
    )


class EconomicFeasibilityReport(BaseModel):
    generated_at: datetime
    reference_capital_eur: float = Field(gt=0)
    risk_fraction: float = Field(gt=0, le=1)
    max_spread_to_stop: float = Field(gt=0)
    max_margin_fraction: float = Field(gt=0, le=1)
    stop_atr_multiples: list[float] = Field(default_factory=list)
    assets: list[AssetEconomicFeasibility] = Field(default_factory=list)
