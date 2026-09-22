from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism


class OpportunityFunnelStrategy(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    signal_rows: int = Field(ge=0)
    blocked_signal_rows: int = Field(ge=0)
    executable_signal_rows: int = Field(ge=0)
    tracked_blocked_probes: int = Field(ge=0)
    resolved_blocked_probes: int = Field(ge=0)
    open_blocked_probes: int = Field(ge=0)
    blocked_wins: int = Field(ge=0)
    blocked_losses: int = Field(ge=0)
    blocked_total_r: float
    blocked_expectancy_r: float
    blocked_feasible_under_max_risk: int = Field(ge=0)
    min_required_capital_base_risk_eur: float | None = Field(default=None, ge=0)
    max_required_capital_base_risk_eur: float | None = Field(default=None, ge=0)
    block_reasons: dict[str, int] = Field(default_factory=dict)


class OpportunityFunnel(BaseModel):
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    signal_rows: int = Field(ge=0)
    blocked_signal_rows: int = Field(ge=0)
    executable_signal_rows: int = Field(ge=0)
    tracked_blocked_probes: int = Field(ge=0)
    resolved_blocked_probes: int = Field(ge=0)
    open_blocked_probes: int = Field(ge=0)
    blocked_wins: int = Field(ge=0)
    blocked_losses: int = Field(ge=0)
    blocked_total_r: float
    blocked_expectancy_r: float
    blocked_feasible_under_max_risk: int = Field(ge=0)
    block_reasons: dict[str, int] = Field(default_factory=dict)
    strategies: list[OpportunityFunnelStrategy] = Field(default_factory=list)
