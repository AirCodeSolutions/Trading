from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.demo_execution import DemoBridgeCommandStatus
from app.domain.trading import Side


class ExecutionAuditEventType(StrEnum):
    OPEN_COMMAND = "open_command"
    CLOSE_COMMAND = "close_command"
    BRIDGE_RESULT = "bridge_result"


class ExecutionAuditEvent(BaseModel):
    event_id: str
    event_type: ExecutionAuditEventType
    at: datetime
    command_id: str
    symbol: str | None = None
    strategy_id: str | None = None
    side: Side | None = None
    lots: float | None = Field(default=None, gt=0)
    reference_entry_price: float | None = Field(default=None, gt=0)
    reference_risk_eur: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    ticket: int = Field(default=0, ge=0)
    status: DemoBridgeCommandStatus | None = None
    error_code: int = Field(default=0, ge=0)
    fill_price: float = Field(default=0.0, ge=0)


class ExecutionQualitySample(BaseModel):
    command_id: str
    at: datetime
    symbol: str
    strategy_id: str
    side: Side
    lots: float = Field(gt=0)
    reference_entry_price: float = Field(gt=0)
    fill_price: float = Field(gt=0)
    slippage_price: float
    adverse_slippage_price: float
    slippage_r: float
    reference_risk_eur: float | None = Field(default=None, gt=0)
    fill_risk_eur: float | None = Field(default=None, gt=0)
    risk_delta_eur: float | None = None
    risk_delta_pct: float | None = None
    reference_reward_risk_ratio: float | None = Field(default=None, ge=0)
    fill_reward_risk_ratio: float | None = Field(default=None, ge=0)
    rr_delta: float | None = None
    ticket: int = Field(gt=0)


class ExecutionQualitySummary(BaseModel):
    commands: int = Field(ge=0)
    fills: int = Field(ge=0)
    refused: int = Field(ge=0)
    errors: int = Field(ge=0)
    unpaired_results: int = Field(ge=0)
    average_adverse_slippage_price: float = Field(ge=0)
    max_adverse_slippage_price: float = Field(ge=0)
    average_slippage_r: float
    average_risk_delta_eur: float = 0.0
    max_risk_increase_eur: float = Field(default=0.0, ge=0)
    max_risk_increase_pct: float = Field(default=0.0, ge=0)
    average_rr_delta: float = 0.0
    minimum_fill_reward_risk_ratio: float = Field(default=0.0, ge=0)
    samples: list[ExecutionQualitySample] = Field(default_factory=list)
