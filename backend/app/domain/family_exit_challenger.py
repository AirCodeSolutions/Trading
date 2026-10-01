from datetime import datetime

from pydantic import BaseModel, Field


class ExitChallengerWindowMetrics(BaseModel):
    paired_trades: int = Field(ge=0)
    champion_total_r: float
    challenger_total_r: float
    delta_total_r: float
    champion_expectancy_r: float
    challenger_expectancy_r: float
    champion_profit_factor: float = Field(ge=0)
    challenger_profit_factor: float = Field(ge=0)
    champion_max_drawdown_r: float = Field(ge=0)
    challenger_max_drawdown_r: float = Field(ge=0)
    champion_targets: int = Field(ge=0)
    challenger_targets: int = Field(ge=0)
    champion_stops: int = Field(ge=0)
    challenger_stops: int = Field(ge=0)
    champion_timeouts: int = Field(ge=0)
    challenger_timeouts: int = Field(ge=0)
    extension_qualified: int = Field(default=0, ge=0)


class FamilyExitChallengerReport(BaseModel):
    generated_at: datetime
    symbol: str
    strategy_id: str
    hypothesis_id: str
    change_axis: str
    champion_target_r: float = Field(gt=0)
    challenger_target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    capital_eur: float = Field(gt=0)
    capital_source: str
    validation: ExitChallengerWindowMetrics
    holdout: ExitChallengerWindowMetrics
    authority_effect: bool = False
    human_review_required: bool = True
    qualification_rule: str | None = None
    limitations: list[str] = Field(default_factory=list)
