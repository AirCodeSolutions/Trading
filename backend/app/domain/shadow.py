from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow_paper import ShadowPaperSummary
from app.domain.trading import Side


class ShadowSignalState(StrEnum):
    NO_SIGNAL = "no_signal"
    SIGNAL_BLOCKED = "signal_blocked"
    SIGNAL_EXECUTABLE = "signal_executable"


class ShadowSizingSnapshot(BaseModel):
    risk_fraction: float = Field(gt=0, le=1)
    approved: bool
    reason: str
    lots: float = Field(ge=0)
    expected_loss_eur: float = Field(ge=0)
    spread_to_stop: float = Field(ge=0)
    capital_eur: float = Field(default=0.0, ge=0)


class ShadowOpportunityDiagnostic(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    evaluated_at: datetime
    latest_closed_m5_at: datetime
    latest_closed_m15_at: datetime
    state: ShadowSignalState
    side: Side | None = None
    regime: MarketRegime
    regime_direction: int = Field(ge=-1, le=1)
    atr_m15: float = Field(ge=0)
    atr_ratio: float = Field(ge=0)
    volatility_percentile: float = Field(ge=0, le=1)
    momentum_12_atr: float | None = None
    efficiency: float = Field(ge=0, le=1)
    break_strength_atr_m5: float | None = None
    retest_depth_atr_m5: float | None = None
    reclaim_atr_m5: float | None = None
    signal_close_location: float | None = Field(default=None, ge=0, le=1)
    structural_stop: float | None = None
    target_r: float | None = Field(default=None, gt=0)
    max_holding_bars: int | None = Field(default=None, gt=0)
    base_risk: ShadowSizingSnapshot | None = None
    max_risk: ShadowSizingSnapshot | None = None
    reason: str


class ShadowCollectionResult(BaseModel):
    appended: bool
    ledger_path: str
    diagnostic: ShadowOpportunityDiagnostic
    paper: ShadowPaperSummary | None = None
