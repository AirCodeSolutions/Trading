from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class OpportunityCaptureState(StrEnum):
    EXECUTABLE = "executable"
    BLOCKED = "blocked"
    MISSED = "missed"


class OpportunityCausalPattern(StrEnum):
    AUCTION_FAILURE_RECLAIM = "auction_failure_reclaim"
    COMPRESSION_BREAKOUT = "compression_breakout"
    DIRECTIONAL_DISPLACEMENT = "directional_displacement"
    STRUCTURAL_EXTREME_STRETCH = "structural_extreme_stretch"
    COMPRESSION_STATE = "compression_state"
    STRUCTURAL_EXTREME = "structural_extreme"
    UNCLASSIFIED = "unclassified"


class OpportunityCausalContext(BaseModel):
    pattern: OpportunityCausalPattern = OpportunityCausalPattern.UNCLASSIFIED
    side: Side | None = None
    aligned_with_move: bool | None = None
    range_position_24: float = Field(default=0.5, ge=0, le=1)
    return_3_atr: float = 0.0
    return_6_atr: float = 0.0
    compression_6_24: float = Field(default=1.0, ge=0)
    body_fraction: float = Field(default=0.0, ge=-1, le=1)
    sweep_atr: float = Field(default=0.0, ge=0)
    reclaim_atr: float = Field(default=0.0, ge=0)
    evidence: list[str] = Field(default_factory=list)


class OpportunityCausalPatternSummary(BaseModel):
    pattern: OpportunityCausalPattern
    episodes: int = Field(ge=0)
    missed: int = Field(ge=0)
    aligned: int = Field(ge=0)
    opposed: int = Field(ge=0)
    no_direction: int = Field(ge=0)
    average_move_atr: float = Field(ge=0)


class TradeIntelligence(BaseModel):
    trade_id: str
    source: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    opened_at: datetime
    exit_at: datetime | None = None
    status: str
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    risk_distance: float = Field(gt=0)
    result_r: float | None = None
    pnl_eur: float | None = None
    mfe_r: float = Field(default=0.0, ge=0)
    mae_r: float = Field(default=0.0, ge=0)
    time_to_mfe_minutes: int | None = Field(default=None, ge=0)
    signal_entry_price: float | None = Field(default=None, gt=0)
    entry_delay_seconds: float = Field(default=0.0, ge=0)
    r_lost_while_waiting: float = 0.0
    rr_at_signal: float | None = None
    rr_at_entry: float | None = None
    mfe_consumed_before_entry_r: float = Field(default=0.0, ge=0)
    block_reason: str | None = None


class MarketOpportunityEpisode(BaseModel):
    episode_id: str
    symbol: str
    side: Side
    birth_at: datetime
    horizon_end_at: datetime
    reference_price: float = Field(gt=0)
    atr_m5: float = Field(gt=0)
    move_atr: float = Field(ge=0)
    capture_state: OpportunityCaptureState
    matching_strategies: list[str] = Field(default_factory=list)
    precursor_first_seen_at: datetime | None = None
    precursor_pattern: OpportunityCausalPattern | None = None
    precursor_lead_minutes: float | None = Field(default=None, ge=0)
    precursor_observations: int = Field(default=0, ge=0)
    causal_context: OpportunityCausalContext = Field(
        default_factory=OpportunityCausalContext
    )


class AssetIntelligence(BaseModel):
    symbol: str
    paper_closed_trades: int = Field(ge=0)
    paper_total_r: float
    blocked_closed_probes: int = Field(ge=0)
    blocked_total_r: float
    market_opportunities: int = Field(ge=0)
    captured_executable: int = Field(ge=0)
    captured_blocked: int = Field(ge=0)
    missed_opportunities: int = Field(ge=0)
    capture_rate: float = Field(ge=0, le=1)
    average_r_lost_while_waiting: float
    average_mfe_r: float = Field(ge=0)
    average_mae_r: float = Field(ge=0)


class TradingIntelligenceOverview(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    market_move_threshold_atr: float = Field(gt=0)
    market_move_horizon_bars: int = Field(gt=0)
    precursor_collection_started_at: datetime | None = None
    precursor_eligible_opportunities: int = Field(default=0, ge=0)
    precursor_seen_opportunities: int = Field(default=0, ge=0)
    precursor_seen_rate: float = Field(default=0.0, ge=0, le=1)
    average_precursor_lead_minutes: float = Field(default=0.0, ge=0)
    trades: list[TradeIntelligence] = Field(default_factory=list)
    opportunities: list[MarketOpportunityEpisode] = Field(default_factory=list)
    assets: list[AssetIntelligence] = Field(default_factory=list)
    causal_patterns: list[OpportunityCausalPatternSummary] = Field(
        default_factory=list
    )
    limitations: list[str] = Field(default_factory=list)
