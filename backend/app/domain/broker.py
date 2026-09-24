from pydantic import BaseModel, Field, model_validator


class BrokerSymbolSpec(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    min_lot: float = Field(gt=0)
    max_lot: float = Field(gt=0)
    lot_step: float = Field(gt=0)
    margin_required: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_market(self) -> "BrokerSymbolSpec":
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        if self.max_lot < self.min_lot:
            raise ValueError("max_lot must be >= min_lot")
        return self

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class PositionSizeRequest(BaseModel):
    spec: BrokerSymbolSpec
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    requested_risk_fraction: float | None = Field(default=None, gt=0, le=1)
    capital_eur: float | None = Field(default=None, gt=0)


class PositionSizeResult(BaseModel):
    approved: bool
    reason: str
    risk_fraction: float
    risk_budget_eur: float
    stop_distance: float
    spread: float
    spread_to_stop: float
    raw_lots: float
    lots: float
    expected_loss_eur: float
    min_lot_loss_eur: float
    estimated_margin_eur: float


class MarketQualityRequest(BaseModel):
    spec: BrokerSymbolSpec
    atr_m5: float = Field(gt=0)
    atr_m15: float = Field(gt=0)
    capital_eur: float | None = Field(default=None, gt=0)


class MarketQualityResult(BaseModel):
    symbol: str
    spread_atr_m5: float
    spread_atr_m15: float
    min_lot_loss_atr_m15_eur: float
    required_capital_base_risk_eur: float = Field(default=0.0, ge=0)
    required_capital_max_risk_eur: float = Field(default=0.0, ge=0)
    minimum_feasible_risk_fraction: float = Field(default=0.0, ge=0)
    default_risk_feasible: bool
    absolute_risk_feasible: bool
    execution_quality_score: float = Field(ge=0, le=100)
    eligible_for_m15_research: bool
    reasons: list[str]
