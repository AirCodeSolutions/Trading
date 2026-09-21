from collections import Counter
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.domain.admission import AdmissionDecision
from app.domain.broker import BrokerSymbolSpec
from app.domain.macro import MacroEvent
from app.domain.trading import Side


class OpportunityMechanism(StrEnum):
    POST_SHOCK_CONTINUATION = "post_shock_continuation"
    BREAK_RETEST_REACCEL = "break_retest_reaccel"
    FAILED_AUCTION_REVERSAL = "failed_auction_reversal"
    DIRECTIONAL_TRANSITION = "directional_transition"
    DIRECTIONAL_PULLBACK_RESUMPTION = "directional_pullback_resumption"
    ASIA_RANGE_SWEEP_REVERSAL = "asia_range_sweep_reversal"


def all_mechanisms() -> list[OpportunityMechanism]:
    return list(OpportunityMechanism)


class ResearchSplit(BaseModel):
    train_end: datetime
    validation_end: datetime

    @model_validator(mode="after")
    def validate_order(self) -> "ResearchSplit":
        if self.train_end.utcoffset() is None or self.validation_end.utcoffset() is None:
            raise ValueError("research split datetimes must be timezone-aware")
        if self.validation_end <= self.train_end:
            raise ValueError("validation_end must be after train_end")
        return self


class OpportunityBacktestConfig(BaseModel):
    spec: BrokerSymbolSpec
    mechanism: OpportunityMechanism
    split: ResearchSplit
    requested_risk_fraction: float | None = Field(default=None, gt=0, le=1)
    slippage_spread_fraction: float = Field(default=0.25, ge=0, le=3)
    macro_events: list[MacroEvent] = Field(default_factory=list)


class Mt4OpportunityBacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    mechanism: OpportunityMechanism
    split: ResearchSplit
    requested_risk_fraction: float | None = Field(default=None, gt=0, le=1)
    slippage_spread_fraction: float = Field(default=0.25, ge=0, le=3)


class PortfolioResearchRequest(BaseModel):
    split: ResearchSplit
    symbols: list[str] | None = None
    mechanisms: list[OpportunityMechanism] = Field(default_factory=all_mechanisms)
    requested_risk_fraction: float | None = Field(default=None, gt=0, le=1)
    slippage_spread_fraction: float = Field(default=0.25, ge=0, le=3)


class OpportunityCandidate(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    entry_at: datetime
    signal_index: int = Field(ge=0)
    entry_index: int = Field(ge=0)
    structural_stop: float = Field(gt=0)
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    reason: str


class TradeOutcome(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    lots: float = Field(gt=0)
    risk_eur: float = Field(gt=0)
    result_r: float
    pnl_eur: float
    execution_cost_r: float = Field(ge=0)
    exit_reason: str


class PerformanceSummary(BaseModel):
    trades: int = Field(ge=0)
    total_r: float
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    win_rate: float = Field(ge=0, le=1)
    max_drawdown_r: float = Field(ge=0)
    total_pnl_eur: float
    average_execution_cost_r: float = Field(ge=0)


class OpportunityBacktestResult(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    candidates: int = Field(ge=0)
    executed: int = Field(ge=0)
    rejected: int = Field(ge=0)
    rejection_reasons: dict[str, int]
    train: PerformanceSummary
    validation: PerformanceSummary
    holdout: PerformanceSummary
    admission: AdmissionDecision


class PortfolioResearchResult(BaseModel):
    results: list[OpportunityBacktestResult]
    skipped_symbols: dict[str, str]
    qualified_strategy_id: str | None
    selection_reason: str


def rejection_counter(values: list[str]) -> dict[str, int]:
    return dict(Counter(values))
