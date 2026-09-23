from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.execution_audit import ExecutionQualitySummary
from app.domain.portfolio import PortfolioAction, ProspectiveQualificationState


class AssetResearchState(StrEnum):
    COLLECT_PROSPECTIVE = "collect_prospective"
    DEGRADED = "degraded"
    RESEARCH_ONLY = "research_only"


class AssetResearchStatus(BaseModel):
    symbol: str
    state: AssetResearchState
    paper_eligible_strategies: list[str] = Field(default_factory=list)
    qualification_states: dict[str, ProspectiveQualificationState] = Field(default_factory=dict)
    market_opportunities_24h: int = Field(ge=0)
    captured_opportunities_24h: int = Field(ge=0)
    missed_opportunities_24h: int = Field(ge=0)
    capture_rate_24h: float = Field(ge=0, le=1)
    blocked_expectancy_r_24h: float
    next_action: str


class DailyTradingReport(BaseModel):
    report_date: date
    generated_at: datetime
    reference_capital_eur: float = Field(gt=0)
    execution_mode: str
    live_trading_enabled: bool
    broker_is_demo: bool
    portfolio_action: PortfolioAction
    portfolio_reason: str
    paper_closed_pnl_eur_today: float
    paper_closed_r_today: float
    paper_open_positions: int = Field(ge=0)
    paper_open_risk_eur: float = Field(ge=0)
    bridge_open_positions: int = Field(ge=0)
    bridge_unrealized_pnl_eur: float
    broker_realized_pnl_eur_today: float | None = None
    broker_closed_trades_today: int = Field(default=0, ge=0)
    broker_history_complete: bool = True
    market_opportunities_24h: int = Field(ge=0)
    captured_opportunities_24h: int = Field(ge=0)
    missed_opportunities_24h: int = Field(ge=0)
    qualification_counts: dict[ProspectiveQualificationState, int] = Field(default_factory=dict)
    execution_quality: ExecutionQualitySummary
    assets: list[AssetResearchStatus] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
