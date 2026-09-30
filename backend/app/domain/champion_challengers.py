from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.asset_specialization import (
    AssetMechanismRole,
    AssetProfileStatus,
    EvidenceAlignment,
)
from app.domain.opportunity import OpportunityMechanism, ResearchSplit


class VariantRole(StrEnum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"


class EconomicChangeAxis(StrEnum):
    ENTRY_TIMING = "entry_timing"
    ENTRY_EXECUTION = "entry_execution"
    EXIT_MANAGEMENT = "exit_management"


class ChallengerEvidenceState(StrEnum):
    NO_EVIDENCE = "no_evidence"
    COLLECTING = "collecting"
    REVIEWABLE = "reviewable"
    DOES_NOT_SUPPORT_REVIEW = "does_not_support_review"
    CONFLICTED = "conflicted"


class VariantMetrics(BaseModel):
    trades: int = 0
    total_r: float | None = None
    expectancy_r: float | None = None
    profit_factor: float | None = None
    max_drawdown_r: float | None = None
    average_mfe_capture: float | None = None
    average_giveback_r: float | None = None
    average_execution_cost_r: float | None = None


class EvidenceChecklist(BaseModel):
    historical_validation_available: bool = False
    historical_holdout_available: bool = False
    prospective_paired_available: bool = False
    execution_cost_evidence_available: bool = False
    human_review_required: bool = True


class ChallengerReport(BaseModel):
    variant_id: str
    role: VariantRole = VariantRole.CHALLENGER
    economic_axis: EconomicChangeAxis
    evidence_state: ChallengerEvidenceState
    paired_n: int = 0
    baseline_metrics: VariantMetrics = Field(default_factory=VariantMetrics)
    challenger_metrics: VariantMetrics = Field(default_factory=VariantMetrics)
    delta_total_r: float | None = None
    delta_expectancy_r: float | None = None
    delta_profit_factor: float | None = None
    delta_drawdown_r: float | None = None
    delta_mfe_capture: float | None = None
    delta_giveback_r: float | None = None
    evidence: EvidenceChecklist = Field(default_factory=EvidenceChecklist)
    reason: str
    auto_promote: bool = False


class ChampionReport(BaseModel):
    variant_id: str = "BASELINE_V1"
    role: VariantRole = VariantRole.CHAMPION
    historical_state: str | None = None
    historical_weakest_expectancy_r: float | None = None
    historical_worst_drawdown_r: float | None = None
    prospective_state: str | None = None
    paper_n: int = 0
    paper_expectancy_r: float | None = None
    paper_profit_factor: float | None = None
    paper_max_drawdown_r: float | None = None
    paper_total_r: float | None = None
    paper_average_execution_cost_r: float | None = None


class ChampionChallengerFamilyReport(BaseModel):
    family_id: str
    symbol: str
    mechanism: OpportunityMechanism
    asset_profile_status: AssetProfileStatus
    asset_role: AssetMechanismRole
    compatibility: bool
    evidence_alignment: EvidenceAlignment
    champion: ChampionReport
    challengers: list[ChallengerReport] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


class ChampionChallengerReport(BaseModel):
    families: list[ChampionChallengerFamilyReport] = Field(default_factory=list)
    family_count: int = 0
    champion_count: int = 0
    challengers_collecting: int = 0
    challengers_reviewable: int = 0
    challengers_does_not_support_review: int = 0
    challengers_conflicted: int = 0


class ChampionChallengerResearchRequest(BaseModel):
    split: ResearchSplit
    symbols: list[str] | None = None
