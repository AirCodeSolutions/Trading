from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import ShadowPaperSummary


class MarketPriceSource(StrEnum):
    BROKER_QUOTE = "broker_quote"
    CLOSED_M5 = "closed_m5"


class MarketUniverseAsset(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    price_source: MarketPriceSource
    as_of: datetime
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    spread: float | None = Field(default=None, ge=0)
    quote_live: bool
    has_m5: bool
    has_m15: bool
    broker_spec_ready: bool
    research_ready: bool
    paper_ready: bool
    reason: str


class ProspectiveQualificationState(StrEnum):
    COLLECTING = "collecting"
    FAILED = "failed"
    SUPPORTS_DEMO = "supports_demo"


class ProspectiveQualification(BaseModel):
    strategy_id: str
    state: ProspectiveQualificationState
    closed_trades: int = Field(ge=0)
    expectancy_r: float
    profit_factor: float = Field(ge=0)
    max_drawdown_r: float = Field(ge=0)
    reason: str


class PaperStrategyRuntime(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    summary: ShadowPaperSummary
    qualification: ProspectiveQualification
    daily_pnl_eur: float = 0.0
    daily_r: float = 0.0


class PortfolioAction(StrEnum):
    NO_TRADE = "no_trade"
    PAPER_ONLY = "paper_only"
    DEMO_ELIGIBLE = "demo_eligible"


class PortfolioDecision(BaseModel):
    at: datetime
    action: PortfolioAction
    selected_strategy_id: str | None = None
    reason: str
    historical_active: bool
    prospective_supports_demo: bool


class PortfolioRiskSnapshot(BaseModel):
    reference_capital_eur: float = Field(gt=0)
    research_paper_closed_pnl_eur: float
    research_paper_total_r: float
    research_paper_open_risk_eur: float = Field(ge=0)
    research_paper_open_positions: int = Field(ge=0)
    selected_daily_pnl_eur: float
    selected_daily_r: float
    selected_open_risk_eur: float = Field(ge=0)
    selected_open_positions: int = Field(ge=0)
    max_daily_loss_eur: float = Field(gt=0)
    remaining_daily_loss_budget_eur: float = Field(ge=0)


class BrokerDemoSnapshot(BaseModel):
    is_demo: bool
    balance: float
    equity: float
    margin: float
    free_margin: float
    observed_positions: int = Field(ge=0)


class TradingOverview(BaseModel):
    at: datetime
    broker: BrokerDemoSnapshot | None
    risk: PortfolioRiskSnapshot
    portfolio: PortfolioDecision
    qualifications: list[ProspectiveQualification]
    paper_strategies: list[PaperStrategyRuntime] = Field(default_factory=list)
