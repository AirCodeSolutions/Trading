from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.opportunity import OpportunityMechanism


class EconomicContractRole(StrEnum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"


class EconomicChangeAxis(StrEnum):
    TARGET_R = "target_r"


class EconomicContract(BaseModel):
    contract_id: str
    version: int = Field(gt=0)
    symbol: str
    mechanism: OpportunityMechanism
    role: EconomicContractRole
    change_axis: EconomicChangeAxis
    target_r: float = Field(gt=0)
    max_holding_bars: int = Field(gt=0)
    description: str


class EconomicVariantMetrics(BaseModel):
    contract_id: str
    role: EconomicContractRole
    closed_trades: int = Field(ge=0)
    total_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = Field(default=0.0, ge=0)
    max_drawdown_r: float = Field(default=0.0, ge=0)


class PairedEconomicComparison(BaseModel):
    pair_id: str
    champion_result_r: float
    challenger_result_r: float
    delta_r: float


class PairedEconomicContractReport(BaseModel):
    family_id: str
    comparison_id: str
    champion: EconomicVariantMetrics
    challenger: EconomicVariantMetrics
    paired_trades: int = Field(ge=0)
    delta_total_r: float = 0.0
    open_pair: bool = False
    comparisons: list[PairedEconomicComparison] = Field(default_factory=list)
    broker_authority: bool = False
    human_review_required: bool = True
