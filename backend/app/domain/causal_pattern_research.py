from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading_intelligence import OpportunityCausalPattern


class CausalPatternSplitSummary(BaseModel):
    episodes: int = Field(ge=0)
    directional_episodes: int = Field(ge=0)
    aligned: int = Field(ge=0)
    opposed: int = Field(ge=0)
    no_direction: int = Field(ge=0)
    alignment_rate: float | None = Field(default=None, ge=0, le=1)
    average_move_atr: float = Field(ge=0)


class CausalPatternHistoricalSummary(BaseModel):
    pattern: OpportunityCausalPattern
    train: CausalPatternSplitSummary
    validation: CausalPatternSplitSummary
    holdout: CausalPatternSplitSummary


class AssetCausalPatternResearch(BaseModel):
    symbol: str
    total_episodes: int = Field(ge=0)
    patterns: list[CausalPatternHistoricalSummary] = Field(default_factory=list)


class CausalPatternResearchReport(BaseModel):
    generated_at: datetime
    train_end: datetime
    validation_end: datetime
    move_threshold_atr: float = Field(gt=0)
    horizon_bars: int = Field(gt=0)
    assets: list[AssetCausalPatternResearch] = Field(default_factory=list)
