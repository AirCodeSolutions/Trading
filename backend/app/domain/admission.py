from enum import StrEnum

from pydantic import BaseModel, Field


class AdmissionState(StrEnum):
    REJECTED = "rejected"
    SHADOW = "shadow"
    ACTIVE = "active"


class EvidenceWindow(BaseModel):
    trades: int = Field(ge=0)
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)


class StrategyEvidence(BaseModel):
    strategy_id: str
    train: EvidenceWindow
    validation: EvidenceWindow
    holdout: EvidenceWindow


class AdmissionDecision(BaseModel):
    strategy_id: str
    state: AdmissionState
    reason: str
    weakest_expectancy_r: float
    worst_drawdown_r: float
