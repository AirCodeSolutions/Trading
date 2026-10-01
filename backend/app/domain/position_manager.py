from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class PositionManagerV2State(StrEnum):
    INITIAL_RISK = "initial_risk"
    NO_FOLLOW_THROUGH = "no_follow_through"
    PROTECT = "protect"
    TRAIL = "trail"
    EXTEND = "extend"
    REGIME_LOSS_EXIT = "regime_loss_exit"
    SAFETY_TIMEOUT = "safety_timeout"
    CLOSED_STOP = "closed_stop"
    CLOSED_TARGET = "closed_target"


class PositionManagerV2Action(StrEnum):
    HOLD = "hold"
    TIGHTEN_STOP = "tighten_stop"
    EXTEND_TARGET = "extend_target"
    EXIT_NO_FOLLOW_THROUGH = "exit_no_follow_through"
    EXIT_REGIME_LOSS = "exit_regime_loss"
    EXIT_SAFETY_TIMEOUT = "exit_safety_timeout"
    CLOSED_STOP = "closed_stop"
    CLOSED_TARGET = "closed_target"


class PositionManagerV2Snapshot(BaseModel):
    trade_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    evaluated_at: datetime
    state: PositionManagerV2State
    entry_price: float
    initial_stop: float
    current_stop: float
    candidate_stop: float | None = None
    initial_target: float
    current_target: float
    candidate_target: float | None = None
    initial_risk_distance: float
    risk_eur: float
    bars_held: int = Field(ge=0)
    favorable_close_r: float
    mfe_r: float
    mae_r: float
    current_result_r: float
    protected: bool
    landmark_type: str | None = None
    landmark_price: float | None = None
    proposed_action: PositionManagerV2Action = PositionManagerV2Action.HOLD
    proposed_exit_price: float | None = None
    proposed_exit_r: float | None = None
    reason: str
    m15_regime: str | None = None
    m15_direction: int | None = None
    maximum_added_risk_r: float = 0.0


class PositionManagerComparison(BaseModel):
    trade_id: str
    symbol: str
    mechanism: OpportunityMechanism
    baseline_result_r: float | None = None
    v2_result_r: float | None = None
    delta_r: float | None = None
    baseline_exit_reason: str | None = None
    v2_exit_reason: str | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    baseline_mfe_r: float | None = None
    baseline_mae_r: float | None = None
    v2_mfe_r: float | None = None
    v2_mae_r: float | None = None
    baseline_mfe_capture: float | None = None
    v2_mfe_capture: float | None = None
    baseline_giveback_r: float | None = None
    v2_giveback_r: float | None = None
    bars_held_baseline: int | None = None
    bars_held_v2: int | None = None
    protected_before_exit: bool = False
    extension_used: bool = False
    no_follow_through_used: bool = False
    regime_loss_used: bool = False
    pending: bool = False
    invalid_data: bool = False
    invalid_reason: str | None = None


class PositionManagerReport(BaseModel):
    window_hours: int
    generated_at: datetime
    trades: int
    pending: int
    comparisons: list[PositionManagerComparison] = Field(default_factory=list)
    baseline_total_r: float = 0.0
    v2_total_r: float = 0.0
    delta_r: float = 0.0
    baseline_expectancy_r: float = 0.0
    v2_expectancy_r: float = 0.0
    baseline_max_drawdown_r: float = 0.0
    v2_max_drawdown_r: float = 0.0
    baseline_average_mfe_capture: float | None = None
    v2_average_mfe_capture: float | None = None
    baseline_average_giveback_r: float = 0.0
    v2_average_giveback_r: float = 0.0
    baseline_profit_factor: float = 0.0
    v2_profit_factor: float = 0.0
    invalid: int = 0
    no_follow_through_count: int = 0
    extension_count: int = 0
    regime_loss_count: int = 0
    by_asset: dict[str, "PositionManagerAggregate"] = Field(default_factory=dict)
    by_mechanism: dict[str, "PositionManagerAggregate"] = Field(default_factory=dict)


class PositionManagerAggregate(BaseModel):
    trades: int = 0
    baseline_total_r: float = 0.0
    v2_total_r: float = 0.0
    delta_r: float = 0.0
    baseline_expectancy_r: float = 0.0
    v2_expectancy_r: float = 0.0
    baseline_profit_factor: float = 0.0
    v2_profit_factor: float = 0.0
    baseline_max_drawdown_r: float = 0.0
    v2_max_drawdown_r: float = 0.0
    average_giveback_r: float = 0.0
    average_mfe_capture: float | None = None
