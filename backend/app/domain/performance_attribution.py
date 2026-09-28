from datetime import datetime

from pydantic import BaseModel, Field


class AttributionCohort(BaseModel):
    population: str
    dimension: str
    value: str
    observations: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    win_rate: float | None = None
    total_r: float | None = None
    expectancy_r: float | None = None
    profit_factor: float | None = None
    max_drawdown_r: float | None = None
    median_win_r: float | None = None
    median_loss_r: float | None = None
    median_mfe_r: float | None = None
    median_mae_r: float | None = None
    median_close1_r: float | None = None
    median_close3_r: float | None = None
    median_holding_bars: float | None = None
    median_spread_to_stop: float | None = None
    median_stop_atr_m15: float | None = None
    best_results_r: list[float] = Field(default_factory=list)
    worst_results_r: list[float] = Field(default_factory=list)
    opposite_results: int = Field(ge=0)


class PerformanceAttributionReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    populations: dict[str, int] = Field(default_factory=dict)
    summaries: list[AttributionCohort] = Field(default_factory=list)
    interactions: list[AttributionCohort] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
