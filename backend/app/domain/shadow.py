from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.macro import MacroSignalContext
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.session_landmark import SessionLandmarkContext
from app.domain.shadow_paper import ShadowPaperSummary
from app.domain.trading import Side


class ShadowSignalState(StrEnum):
    NO_SIGNAL = "no_signal"
    SIGNAL_BLOCKED = "signal_blocked"
    SIGNAL_EXECUTABLE = "signal_executable"


class StopGeometrySource(StrEnum):
    ATR_DISTANCE = "atr_distance"
    ATR_DISTANCE_WITH_SPREAD = "atr_distance_with_spread"
    RAW_STRUCTURE = "raw_structure"
    RAW_STRUCTURE_WITH_SPREAD = "raw_structure_with_spread"
    RAW_STRUCTURE_FLOOR_COMPARISON = "raw_structure_floor_comparison"
    RAW_STRUCTURE_FLOOR_COMPARISON_WITH_SPREAD = "raw_structure_floor_comparison_with_spread"


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
    raw_stop_price: float | None = None
    stop_geometry_source: StopGeometrySource | None = None
    stop_atr_distance: float | None = None
    atr_m5: float | None = None
    structural_stop_distance: float | None = None
    structural_stop_atr_m5: float | None = None
    structural_stop_atr_m15: float | None = None
    spread_at_signal: float | None = None
    spread_atr_m5: float | None = None
    spread_atr_m15: float | None = None
    broker_digits: int | None = None
    broker_tick_size: float | None = None
    session_landmark_context: SessionLandmarkContext | None = None
    target_r: float | None = Field(default=None, gt=0)
    max_holding_bars: int | None = Field(default=None, gt=0)
    base_risk: ShadowSizingSnapshot | None = None
    max_risk: ShadowSizingSnapshot | None = None
    macro_context: MacroSignalContext | None = None
    reason: str


class ShadowCollectionResult(BaseModel):
    appended: bool
    ledger_path: str
    diagnostic: ShadowOpportunityDiagnostic
    paper: ShadowPaperSummary | None = None
