from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus
from app.domain.trading import Side


class BlockedOpportunityProbe(BaseModel):
    probe_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    opened_at: datetime
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    spread_at_entry: float = Field(ge=0)
    risk_distance: float = Field(gt=0)
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    block_reason: str
    max_risk_approved: bool
    max_risk_reason: str | None = None
    status: PaperTradeStatus = PaperTradeStatus.OPEN
    exit_at: datetime | None = None
    exit_price: float | None = None
    result_r: float | None = None
    bars_held: int = Field(default=0, ge=0)


class BlockedProbeState(BaseModel):
    last_started_signal_at: datetime | None = None
    open_probe: BlockedOpportunityProbe | None = None


class BlockedProbeSummary(BaseModel):
    closed_probes: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    open_probe: BlockedOpportunityProbe | None = None
    recent_probes: list[BlockedOpportunityProbe] = Field(default_factory=list)


class BlockedProbeRuntime(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    summary: BlockedProbeSummary
