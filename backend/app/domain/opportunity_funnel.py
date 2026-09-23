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
    tracked_unqualified_probes: int = Field(default=0, ge=0)
    resolved_unqualified_probes: int = Field(default=0, ge=0)
    open_unqualified_probes: int = Field(default=0, ge=0)
    unqualified_probe_wins: int = Field(default=0, ge=0)
    unqualified_probe_losses: int = Field(default=0, ge=0)
    unqualified_probe_total_r: float = 0.0
    unqualified_probe_expectancy_r: float = 0.0
    tracked_blocked_probes: int = Field(ge=0)
    resolved_blocked_probes: int = Field(ge=0)
    open_blocked_probes: int = Field(ge=0)
    blocked_wins: int = Field(ge=0)
    blocked_losses: int = Field(ge=0)
    blocked_total_r: float
    blocked_expectancy_r: float
    blocked_feasible_under_max_risk: int = Field(ge=0)
    capital_limited_probes: int = Field(default=0, ge=0)
    capital_base_feasible_probes: int = Field(default=0, ge=0)
    capital_max_feasible_probes: int = Field(default=0, ge=0)
    capital_base_feasible_resolved_probes: int = Field(default=0, ge=0)
    capital_base_feasible_wins: int = Field(default=0, ge=0)
    capital_base_feasible_losses: int = Field(default=0, ge=0)
    capital_base_feasible_total_r: float = 0.0
    capital_base_feasible_expectancy_r: float = 0.0
    min_required_capital_base_risk_eur: float | None = Field(default=None, ge=0)
    max_required_capital_base_risk_eur: float | None = Field(default=None, ge=0)
    block_reasons: dict[str, int] = Field(default_factory=dict)


class OpportunityFunnel(BaseModel):
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    reference_capital_eur: float = Field(gt=0)
    base_risk_budget_eur: float = Field(ge=0)
    absolute_max_risk_budget_eur: float = Field(ge=0)
    signal_rows: int = Field(ge=0)
    blocked_signal_rows: int = Field(ge=0)
    executable_signal_rows: int = Field(ge=0)
    tracked_unqualified_probes: int = Field(default=0, ge=0)
    resolved_unqualified_probes: int = Field(default=0, ge=0)
    open_unqualified_probes: int = Field(default=0, ge=0)
    unqualified_probe_wins: int = Field(default=0, ge=0)
    unqualified_probe_losses: int = Field(default=0, ge=0)
    unqualified_probe_total_r: float = 0.0
    unqualified_probe_expectancy_r: float = 0.0
    tracked_blocked_probes: int = Field(ge=0)
    resolved_blocked_probes: int = Field(ge=0)
    open_blocked_probes: int = Field(ge=0)
    blocked_wins: int = Field(ge=0)
    blocked_losses: int = Field(ge=0)
    blocked_total_r: float
    blocked_expectancy_r: float
    blocked_feasible_under_max_risk: int = Field(ge=0)
    capital_limited_probes: int = Field(default=0, ge=0)
    capital_base_feasible_probes: int = Field(default=0, ge=0)
    capital_max_feasible_probes: int = Field(default=0, ge=0)
    capital_base_feasible_resolved_probes: int = Field(default=0, ge=0)
    capital_base_feasible_wins: int = Field(default=0, ge=0)
    capital_base_feasible_losses: int = Field(default=0, ge=0)
    capital_base_feasible_total_r: float = 0.0
    capital_base_feasible_expectancy_r: float = 0.0
    block_reasons: dict[str, int] = Field(default_factory=dict)
    strategies: list[OpportunityFunnelStrategy] = Field(default_factory=list)
