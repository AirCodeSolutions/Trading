from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.admission import AdmissionState
from app.domain.opportunity import OpportunityMechanism, PortfolioResearchResult, ResearchSplit


class AssetMechanismRole(StrEnum):
    PRIMARY_HYPOTHESIS = "primary_hypothesis"
    SECONDARY_HYPOTHESIS = "secondary_hypothesis"
    GENERIC_BASELINE = "generic_baseline"


class EvidenceAlignment(StrEnum):
    NO_EVIDENCE = "no_evidence"
    HISTORICAL_ONLY = "historical_only"
    PROSPECTIVE_COLLECTING = "prospective_collecting"
    PROSPECTIVE_ONLY = "prospective_only"
    HISTORICAL_AND_PROSPECTIVE = "historical_and_prospective"
    CONFLICTED = "conflicted"


class AssetProfileStatus(StrEnum):
    STANDARD = "standard"
    VIABILITY_RESEARCH = "viability_research"


class AssetMechanismEvidence(BaseModel):
    mechanism: OpportunityMechanism
    role: AssetMechanismRole
    compatible: bool = True
    compatibility_reason: str | None = None
    strategy_id: str
    historical_state: AdmissionState | None = None
    weakest_historical_expectancy_r: float | None = None
    historical_worst_drawdown_r: float | None = None
    historical_paper_collection_candidate: bool | None = None
    prospective_state: str | None = None
    paper_n: int = Field(default=0, ge=0)
    paper_expectancy_r: float | None = None
    paper_profit_factor: float | None = None
    paper_max_drawdown_r: float | None = None
    paper_total_r: float | None = None
    paper_pnl_eur: float | None = None
    open_trade: bool = False
    shadow_state: str | None = None
    shadow_side: str | None = None
    shadow_reason: str | None = None
    evidence_alignment: EvidenceAlignment = EvidenceAlignment.NO_EVIDENCE
    pm_trades: int | None = None
    pm_delta_r: float | None = None
    pm_baseline_giveback_r: float | None = None
    pm_v2_giveback_r: float | None = None
    pm_baseline_mfe_capture: float | None = None
    pm_v2_mfe_capture: float | None = None


class AssetSpecializationSnapshot(BaseModel):
    symbol: str
    profile_version: str = "asset-playbook-v2"
    profile_status: AssetProfileStatus = AssetProfileStatus.STANDARD
    primary_mechanisms: list[OpportunityMechanism] = Field(default_factory=list)
    secondary_mechanisms: list[OpportunityMechanism] = Field(default_factory=list)
    mechanism_evidence: list[AssetMechanismEvidence] = Field(default_factory=list)
    evidence_reason: str


class AssetSpecializationResearchRequest(BaseModel):
    split: ResearchSplit
    symbols: list[str] | None = None


class AssetSpecializationResearchRow(BaseModel):
    symbol: str
    mechanism: OpportunityMechanism
    role: AssetMechanismRole
    candidates: int
    executed: int
    rejected: int
    rejection_reasons: dict[str, int]
    validation_trades: int
    validation_expectancy_r: float
    validation_profit_factor: float
    validation_max_drawdown_r: float
    validation_average_execution_cost_r: float
    holdout_trades: int
    holdout_expectancy_r: float
    holdout_profit_factor: float
    holdout_max_drawdown_r: float
    holdout_average_execution_cost_r: float
    admission_state: AdmissionState


class AssetSpecializationResearchResult(BaseModel):
    rows: list[AssetSpecializationResearchRow]
    raw_portfolio_result: PortfolioResearchResult
