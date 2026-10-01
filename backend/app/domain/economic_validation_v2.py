from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.execution_audit import ExecutionQualitySummary
from app.domain.opportunity import OpportunityMechanism


class EconomicEvidenceState(StrEnum):
    NO_EVIDENCE = "no_evidence"
    COLLECTING = "collecting"
    NEGATIVE = "negative"
    SUPPORTS_DEMO_EVALUATION = "supports_demo_evaluation"


class TradeEconomics(BaseModel):
    trades: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    total_r: float = 0.0
    expectancy_r: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    max_drawdown_r: float = Field(default=0.0, ge=0)
    total_pnl_eur: float = 0.0


class FamilyEconomicValidation(BaseModel):
    strategy_id: str
    symbol: str
    mechanism: OpportunityMechanism
    asset_role: str
    evidence_state: EconomicEvidenceState
    historical_state: str | None = None
    prospective_state: str | None = None
    paper: TradeEconomics = Field(default_factory=TradeEconomics)
    signal_rows: int = Field(default=0, ge=0)
    executable_signal_rows: int = Field(default=0, ge=0)
    blocked_signal_rows: int = Field(default=0, ge=0)
    unqualified_probe_trades: int = Field(default=0, ge=0)
    unqualified_probe_total_r: float = 0.0
    blocked_probe_trades: int = Field(default=0, ge=0)
    blocked_probe_total_r: float = 0.0
    pm_paired_trades: int = Field(default=0, ge=0)
    pm_baseline_total_r: float | None = None
    pm_v2_total_r: float | None = None
    pm_delta_r: float | None = None
    pm_baseline_mfe_r: float | None = None
    pm_v2_mfe_r: float | None = None
    pm_baseline_mae_r: float | None = None
    pm_v2_mae_r: float | None = None
    pm_baseline_mfe_capture: float | None = None
    pm_v2_mfe_capture: float | None = None
    pm_baseline_giveback_r: float | None = None
    pm_v2_giveback_r: float | None = None
    reviewable_challengers: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


class OperationalDeploymentGate(BaseModel):
    drain_enabled: bool
    paper_open_positions: int = Field(ge=0)
    bridge_open_positions: int = Field(ge=0)
    pending_open_command: bool
    pending_close_command: bool
    book_flat: bool
    research_stack_deploy_ready: bool
    reason: str
class EconomicValidationReport(BaseModel):
    generated_at: datetime
    window_hours: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    capital_eur: float = Field(gt=0)
    capital_source: str
    paper: TradeEconomics
    paper_open_positions: int = Field(ge=0)
    paper_open_risk_eur: float = Field(ge=0)
    bridge_open_positions: int = Field(ge=0)
    bridge_unrealized_pnl_eur: float
    broker_realized_pnl_eur_today: float | None = None
    broker_closed_trades_window: int = Field(default=0, ge=0)
    broker_realized_pnl_eur_window: float | None = None
    broker_missing_tickets_window: list[int] = Field(default_factory=list)
    broker_history_complete: bool
    signal_rows: int = Field(ge=0)
    executable_signal_rows: int = Field(ge=0)
    blocked_signal_rows: int = Field(ge=0)
    block_reasons: dict[str, int] = Field(default_factory=dict)
    unqualified_probe_trades: int = Field(ge=0)
    unqualified_probe_total_r: float
    blocked_probe_trades: int = Field(ge=0)
    blocked_probe_total_r: float
    pm_paired_trades: int = Field(ge=0)
    pm_baseline_total_r: float
    pm_v2_total_r: float
    pm_delta_r: float
    execution_quality: ExecutionQualitySummary
    families_supporting_demo: int = Field(ge=0)
    families_failed: int = Field(ge=0)
    families_collecting: int = Field(ge=0)
    economic_state: EconomicEvidenceState
    v2_authority_cutover_supported: bool
    v2_authority_gaps: list[str] = Field(default_factory=list)
    allocator_ready: bool
    allocator_selected_strategy_ids: list[str] = Field(default_factory=list)
    deployment: OperationalDeploymentGate
    families: list[FamilyEconomicValidation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
