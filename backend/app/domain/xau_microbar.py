from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.macro import MacroSignalContext
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowSignalState
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern


class XauMicrobarM1(BaseModel):
    minute_at: datetime
    first_quote_at: datetime
    last_quote_at: datetime
    bid_open: float = Field(gt=0)
    bid_high: float = Field(gt=0)
    bid_low: float = Field(gt=0)
    bid_close: float = Field(gt=0)
    ask_open: float = Field(gt=0)
    ask_high: float = Field(gt=0)
    ask_low: float = Field(gt=0)
    ask_close: float = Field(gt=0)
    mid_open: float = Field(gt=0)
    mid_high: float = Field(gt=0)
    mid_low: float = Field(gt=0)
    mid_close: float = Field(gt=0)
    spread_open: float = Field(ge=0)
    spread_high: float = Field(ge=0)
    spread_low: float = Field(ge=0)
    spread_close: float = Field(ge=0)
    spread_sum: float = Field(ge=0)
    quote_count: int = Field(gt=0)
    mid_up_ticks: int = Field(default=0, ge=0)
    mid_down_ticks: int = Field(default=0, ge=0)

    @property
    def average_spread(self) -> float:
        return self.spread_sum / self.quote_count

    @property
    def directional_tick_samples(self) -> int:
        return self.mid_up_ticks + self.mid_down_ticks

    @property
    def mid_tick_imbalance(self) -> float | None:
        total = self.directional_tick_samples
        if total == 0:
            return None
        return (self.mid_up_ticks - self.mid_down_ticks) / total


class XauMicrobarState(BaseModel):
    started_at: datetime
    last_quote_at: datetime | None = None
    total_quote_samples: int = Field(default=0, ge=0)
    current_bar: XauMicrobarM1 | None = None


class XauMicrobarGeometry(BaseModel):
    window_minutes: int = Field(gt=0)
    bars: int = Field(gt=0)
    start_at: datetime
    end_at: datetime
    mid_open: float = Field(gt=0)
    mid_high: float = Field(gt=0)
    mid_low: float = Field(gt=0)
    mid_close: float = Field(gt=0)
    range_price: float = Field(ge=0)
    signed_move: float
    close_location: float = Field(ge=0, le=1)
    path_efficiency: float = Field(ge=0, le=1)
    average_spread: float = Field(ge=0)
    max_spread: float = Field(ge=0)
    average_quotes_per_bar: float = Field(ge=0)
    directional_tick_samples: int = Field(default=0, ge=0)
    mid_tick_imbalance: float | None = Field(default=None, ge=-1, le=1)
    spread_change: float = 0.0
    distance_to_low: float = Field(ge=0)
    distance_to_high: float = Field(ge=0)


class XauSequenceMicrostructureSnapshot(BaseModel):
    strategy_id: str
    mechanism: OpportunityMechanism
    signal_at: datetime
    evaluated_at: datetime
    state: ShadowSignalState
    side: Side | None = None
    latest_microbar_at: datetime | None = None
    macro_context: MacroSignalContext | None = None
    geometry_5m: XauMicrobarGeometry | None = None
    geometry_15m: XauMicrobarGeometry | None = None


class XauUnseenTransitionSnapshot(BaseModel):
    episode_id: str
    birth_at: datetime
    episode_side: Side
    move_atr: float = Field(ge=0)
    latest_microbar_at: datetime
    geometry_5m: XauMicrobarGeometry
    geometry_15m: XauMicrobarGeometry | None = None
    transition_pattern: OpportunityCausalPattern | None = None
    transition_side: Side | None = None
    transition_at: datetime | None = None
    transition_bars_waited: int | None = Field(default=None, ge=1)
    transition_aligned: bool | None = None
    move_consumed_atr: float | None = None


class UnseenTransitionResearchSummary(BaseModel):
    symbol: str
    episodes: int = Field(ge=0)
    resolved: int = Field(ge=0)
    aligned: int = Field(ge=0)
    opposed: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    alignment_rate: float | None = Field(default=None, ge=0, le=1)
    median_transition_bars: float | None = Field(default=None, ge=0)
    median_move_consumed_atr: float | None = None
    median_aligned_move_consumed_atr: float | None = None


class UnseenTickPressureResearchSummary(BaseModel):
    symbol: str
    episodes_with_tick_pressure: int = Field(ge=0)
    resolved_with_tick_pressure: int = Field(ge=0)
    aligned_with_tick_pressure: int = Field(ge=0)
    opposed_with_tick_pressure: int = Field(ge=0)
    unresolved_with_tick_pressure: int = Field(ge=0)
    median_directional_tick_samples_5m: float | None = Field(default=None, ge=0)
    median_side_aligned_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_aligned_side_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_opposed_side_tick_imbalance_5m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_directional_tick_samples_15m: float | None = Field(default=None, ge=0)
    median_side_aligned_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_aligned_side_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )
    median_opposed_side_tick_imbalance_15m: float | None = Field(
        default=None, ge=-1, le=1
    )


class XauMicrobarSummary(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "M1"
    started_at: datetime | None = None
    healthy: bool = False
    quote_age_seconds: float | None = Field(default=None, ge=0)
    last_quote_at: datetime | None = None
    total_quote_samples: int = Field(default=0, ge=0)
    closed_bars: int = Field(default=0, ge=0)
    latest_closed_bar_at: datetime | None = None
    current_bar: XauMicrobarM1 | None = None
    geometry_5m: XauMicrobarGeometry | None = None
    geometry_15m: XauMicrobarGeometry | None = None
    sequence_signal_snapshots: int = Field(default=0, ge=0)
    recent_sequence_signals: list[XauSequenceMicrostructureSnapshot] = Field(
        default_factory=list
    )
    unseen_transition_snapshots: int = Field(default=0, ge=0)
    recent_unseen_transitions: list[XauUnseenTransitionSnapshot] = Field(
        default_factory=list
    )
    recent: list[XauMicrobarM1] = Field(default_factory=list)
