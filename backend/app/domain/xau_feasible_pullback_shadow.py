from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.trading import Side


class FeasiblePullbackStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    NO_FILL = "no_fill"
    STOP = "stop"
    TARGET = "target"
    TIMEOUT = "timeout"


class XauFeasiblePullbackProbe(BaseModel):
    probe_id: str
    signal_at: datetime
    side: Side
    stop_price: float = Field(gt=0)
    limit_entry: float = Field(gt=0)
    target_price: float = Field(gt=0)
    spread_at_entry: float = Field(ge=0)
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    fill_window_bars: int = Field(default=3, gt=0)
    risk_eur: float = Field(gt=0)
    status: FeasiblePullbackStatus = FeasiblePullbackStatus.PENDING
    fill_at: datetime | None = None
    exit_at: datetime | None = None
    exit_price: float | None = None
    result_r: float | None = None
    bars_held: int = Field(default=0, ge=0)


class XauFeasiblePullbackState(BaseModel):
    started_at: datetime
    last_started_signal_at: datetime | None = None
    open_probe: XauFeasiblePullbackProbe | None = None


class XauFeasiblePullbackSummary(BaseModel):
    strategy_id: str
    started_at: datetime | None = None
    resolved: int = Field(ge=0)
    filled: int = Field(ge=0)
    no_fill: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    total_r: float = 0.0
    expectancy_r: float = 0.0
    open_probe: XauFeasiblePullbackProbe | None = None
    recent: list[XauFeasiblePullbackProbe] = Field(default_factory=list)
