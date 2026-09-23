from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.trading import Side


class TrailingManagerConfig(BaseModel):
    enable_stop_trailing: bool = True
    enable_target_extension: bool = False
    target_extension_requires_protected_stop: bool = True
    structure_window: int = Field(default=3, ge=2, le=12)
    atr_window: int = Field(default=14, ge=3, le=100)
    atr_buffer_multiple: float = Field(default=0.25, ge=0, le=2)
    break_even_activation_r: float = Field(default=0.75, ge=0)
    target_extension_activation_r: float = Field(default=0.60, ge=0)
    extended_target_r: float = Field(default=1.50, gt=0)


class TrailingAdjustment(BaseModel):
    at: datetime
    side: Side
    favorable_close_r: float
    stop_before: float
    stop_after: float
    target_before: float
    target_after: float
    atr: float
    reason: str


class TrailingReplayResult(BaseModel):
    result_r: float
    pnl_eur: float
    exit_reason: str
    bars_held: int = Field(ge=0)
    final_stop: float
    final_target: float
    adjustments: list[TrailingAdjustment] = Field(default_factory=list)
    maximum_added_risk_r: float = Field(default=0.0, ge=0)
