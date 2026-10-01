from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side


class CorrelationBucket(StrEnum):
    CRYPTO_USD = "crypto_usd"
    USD_FX = "usd_fx"
    USD_METALS = "usd_metals"


class AllocationDecision(StrEnum):
    ALLOCATED = "allocated"
    SKIPPED_NOT_ELIGIBLE = "skipped_not_eligible"
    SKIPPED_SYMBOL_CONCENTRATION = "skipped_symbol_concentration"
    SKIPPED_RISK_BUDGET = "skipped_risk_budget"
    SKIPPED_LOT_CAP = "skipped_lot_cap"
    CAPITAL_UNAVAILABLE = "capital_unavailable"
class PortfolioAllocationRow(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    side: Side
    risk_eur: float = Field(gt=0)
    lots: float = Field(gt=0)
    correlation_bucket: CorrelationBucket
    decision: AllocationDecision
    reason: str
    projected_total_open_risk_eur: float = Field(ge=0)
    projected_total_open_risk_fraction: float | None = Field(default=None, ge=0)
    projected_bucket_risk_eur: float = Field(ge=0)
    concentration_warning: bool = False


class PortfolioOpportunityAllocationReport(BaseModel):
    at: datetime
    ready: bool
    capital_eur: float | None = Field(default=None, gt=0)
    capital_source: str
    max_total_open_risk_fraction: float = Field(gt=0)
    max_total_open_risk_eur: float | None = Field(default=None, gt=0)
    current_open_risk_eur: float = Field(default=0, ge=0)
    current_open_risk_fraction: float | None = Field(default=None, ge=0)
    bridge_open_positions: int = Field(default=0, ge=0)
    selected_strategy_ids: list[str] = Field(default_factory=list)
    primary_strategy_id: str | None = None
    bucket_risk_eur: dict[str, float] = Field(default_factory=dict)
    risk_unknown_symbols: list[str] = Field(default_factory=list)
    uses_daily_loss_cap: bool = False
    rows: list[PortfolioAllocationRow] = Field(default_factory=list)
    reason: str
