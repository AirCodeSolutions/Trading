from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowSignalState
from app.domain.trading import Side


class OpportunityCaptureState(StrEnum):
    EXECUTABLE = "executable"
    BLOCKED = "blocked"
    MISSED = "missed"


class OpportunityDetectionStage(StrEnum):
    UNSEEN = "unseen"
    PRECURSOR_ONLY = "precursor_only"
    SIGNAL_BLOCKED = "signal_blocked"
    SIGNAL_EXECUTABLE = "signal_executable"


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


class UnseenOpportunityPatternSummary(BaseModel):
    pattern: OpportunityCausalPattern
    episodes: int = Field(ge=0)
    buy_episodes: int = Field(ge=0)
    sell_episodes: int = Field(ge=0)
    symbols: dict[str, int] = Field(default_factory=dict)
    average_move_atr: float = Field(ge=0)
    opposed_context_rate: float = Field(ge=0, le=1)
    neutral_context_rate: float = Field(ge=0, le=1)
    average_abs_return_6_atr: float = Field(ge=0)
    average_compression_6_24: float = Field(ge=0)


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
    detection_stage: OpportunityDetectionStage = OpportunityDetectionStage.UNSEEN
    matching_strategies: list[str] = Field(default_factory=list)
    first_signal_at: datetime | None = None
    first_signal_state: ShadowSignalState | None = None
    first_signal_strategy_id: str | None = None
    first_signal_mechanism: OpportunityMechanism | None = None
    first_signal_price: float | None = Field(default=None, gt=0)
    signal_lead_lag_minutes: float | None = None
    move_consumed_at_signal_atr: float | None = Field(default=None, ge=0)
    move_remaining_after_signal_atr: float | None = Field(default=None, ge=0)
    move_consumed_fraction: float | None = Field(default=None, ge=0, le=1)
    precursor_first_seen_at: datetime | None = None
    precursor_pattern: OpportunityCausalPattern | None = None
    precursor_lead_minutes: float | None = Field(default=None, ge=0)
    precursor_observations: int = Field(default=0, ge=0)
    precursor_to_signal_minutes: float | None = Field(default=None, ge=0)
    causal_context: OpportunityCausalContext = Field(
        default_factory=OpportunityCausalContext
    )


class OpportunityWaitingSummary(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    episodes_with_signal: int = Field(ge=0)
    executable_signals: int = Field(ge=0)
    blocked_signals: int = Field(ge=0)
    precursor_then_signal_episodes: int = Field(ge=0)
    average_signal_lead_lag_minutes: float
    average_move_atr: float = Field(ge=0)
    average_move_consumed_at_signal_atr: float = Field(ge=0)
    average_move_remaining_after_signal_atr: float = Field(ge=0)
    average_move_consumed_fraction: float = Field(ge=0, le=1)
    average_precursor_to_signal_minutes: float = Field(ge=0)


class WaitingEarlyContextEpisode(BaseModel):
    episode_id: str
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    first_signal_at: datetime
    signal_lead_lag_minutes: float
    move_consumed_fraction: float = Field(ge=0, le=1)
    move_consumed_at_signal_atr: float = Field(ge=0)
    move_remaining_after_signal_atr: float = Field(ge=0)
    directional_tick_samples_5m: int = Field(default=0, ge=0)
    side_aligned_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    directional_tick_samples_15m: int = Field(default=0, ge=0)
    side_aligned_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )
    precursor_first_seen_at: datetime | None = None
    precursor_pattern: OpportunityCausalPattern | None = None
    precursor_lead_minutes_to_signal: float | None = Field(default=None, ge=0)


class WaitingEarlyContextSummary(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    waiting_episodes: int = Field(ge=0)
    m1_eligible_episodes: int = Field(ge=0)
    tick_pressure_eligible_episodes: int = Field(ge=0)
    early_reaction_m1_episodes: int = Field(ge=0)
    target_band_m1_episodes: int = Field(ge=0)
    target_band_tick_pressure_episodes: int = Field(ge=0)
    late_reaction_m1_episodes: int = Field(ge=0)
    target_band_with_precursor: int = Field(ge=0)
    target_band_precursor_rate: float | None = Field(default=None, ge=0, le=1)
    median_target_directional_tick_samples_5m: float | None = Field(
        default=None, ge=0
    )
    median_target_side_aligned_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_early_side_aligned_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    target_minus_early_tick_imbalance_5m: float | None = Field(
        default=None, ge=-2, le=2
    )
    median_target_side_aligned_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_early_side_aligned_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )


class WaitingEarlyContextReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    target_band_min_fraction: float = Field(ge=0, le=1)
    target_band_max_fraction: float = Field(ge=0, le=1)
    m1_coverage_started_at: dict[str, datetime] = Field(default_factory=dict)
    waiting_episodes: int = Field(ge=0)
    m1_eligible_episodes: int = Field(ge=0)
    tick_pressure_eligible_episodes: int = Field(ge=0)
    target_band_episodes: int = Field(ge=0)
    target_band_m1_eligible_episodes: int = Field(ge=0)
    target_band_tick_pressure_eligible_episodes: int = Field(ge=0)
    target_band_with_precursor: int = Field(ge=0)
    summaries: list[WaitingEarlyContextSummary] = Field(default_factory=list)
    recent_m1_episodes: list[WaitingEarlyContextEpisode] = Field(
        default_factory=list
    )
    limitations: list[str] = Field(default_factory=list)


class ProbeEarlyContextEpisode(BaseModel):
    trade_id: str
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    status: str
    result_r: float
    directional_tick_samples_5m: int = Field(default=0, ge=0)
    side_aligned_tick_imbalance_5m: float | None = Field(default=None, ge=-1, le=1)
    directional_tick_samples_15m: int = Field(default=0, ge=0)
    side_aligned_tick_imbalance_15m: float | None = Field(default=None, ge=-1, le=1)
    pressure_agreement_5m_15m: bool | None = None
    spread_to_risk: float = Field(ge=0)
    average_quotes_per_bar_5m: float = Field(ge=0)
    path_efficiency_5m: float = Field(ge=0, le=1)
    precursor_first_seen_at: datetime | None = None
    precursor_pattern: OpportunityCausalPattern | None = None
    precursor_lead_minutes_to_signal: float | None = Field(default=None, ge=0)


class ProbeEarlyContextSummary(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    resolved_probes: int = Field(ge=0)
    m1_eligible_probes: int = Field(ge=0)
    tick_pressure_eligible_probes: int = Field(ge=0)
    tick_pressure_wins: int = Field(ge=0)
    tick_pressure_losses: int = Field(ge=0)
    tick_pressure_total_r: float = 0.0
    tick_pressure_expectancy_r: float = 0.0
    winner_median_side_aligned_tick_imbalance_5m: float | None = Field(default=None, ge=-1, le=1)
    loser_median_side_aligned_tick_imbalance_5m: float | None = Field(default=None, ge=-1, le=1)
    winner_minus_loser_tick_imbalance_5m: float | None = Field(default=None, ge=-2, le=2)
    winner_median_side_aligned_tick_imbalance_15m: float | None = Field(default=None, ge=-1, le=1)
    loser_median_side_aligned_tick_imbalance_15m: float | None = Field(default=None, ge=-1, le=1)
    winner_pressure_agreement_rate: float | None = Field(default=None, ge=0, le=1)
    loser_pressure_agreement_rate: float | None = Field(default=None, ge=0, le=1)
    winner_median_spread_to_risk: float | None = Field(default=None, ge=0)
    loser_median_spread_to_risk: float | None = Field(default=None, ge=0)
    winner_median_path_efficiency_5m: float | None = Field(default=None, ge=0, le=1)
    loser_median_path_efficiency_5m: float | None = Field(default=None, ge=0, le=1)
    winner_precursor_rate: float | None = Field(default=None, ge=0, le=1)
    loser_precursor_rate: float | None = Field(default=None, ge=0, le=1)
    winner_precursor_patterns: dict[str, int] = Field(default_factory=dict)
    loser_precursor_patterns: dict[str, int] = Field(default_factory=dict)


class ProbeEarlyContextReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    resolved_probes: int = Field(ge=0)
    m1_eligible_probes: int = Field(ge=0)
    tick_pressure_eligible_probes: int = Field(ge=0)
    tick_pressure_wins: int = Field(ge=0)
    tick_pressure_losses: int = Field(ge=0)
    summaries: list[ProbeEarlyContextSummary] = Field(default_factory=list)
    recent_tick_pressure_probes: list[ProbeEarlyContextEpisode] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


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
    precursor_only_opportunities: int = Field(default=0, ge=0)
    precursor_unseen_opportunities: int = Field(default=0, ge=0)
    precursor_signal_blocked_opportunities: int = Field(default=0, ge=0)
    precursor_signal_executable_opportunities: int = Field(default=0, ge=0)
    signal_without_precursor_opportunities: int = Field(default=0, ge=0)
    precursor_to_signal_conversion_rate: float = Field(default=0.0, ge=0, le=1)
    average_precursor_lead_minutes: float = Field(default=0.0, ge=0)
    trades: list[TradeIntelligence] = Field(default_factory=list)
    opportunities: list[MarketOpportunityEpisode] = Field(default_factory=list)
    assets: list[AssetIntelligence] = Field(default_factory=list)
    causal_patterns: list[OpportunityCausalPatternSummary] = Field(
        default_factory=list
    )
    unseen_patterns: list[UnseenOpportunityPatternSummary] = Field(
        default_factory=list
    )
    waiting_costs: list[OpportunityWaitingSummary] = Field(default_factory=list)
    waiting_early_context: WaitingEarlyContextReport | None = None
    probe_early_context: ProbeEarlyContextReport | None = None
    limitations: list[str] = Field(default_factory=list)
