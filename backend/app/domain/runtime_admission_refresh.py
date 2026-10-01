from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AdmissionRefreshChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class RuntimeAdmissionRefreshChange(BaseModel):
    strategy_id: str
    change_type: AdmissionRefreshChangeType
    before_state: str | None = None
    after_state: str | None = None
    before_weakest_expectancy_r: float | None = None
    after_weakest_expectancy_r: float | None = None
    before_worst_drawdown_r: float | None = None
    after_worst_drawdown_r: float | None = None
    before_paper_collection_candidate: bool | None = None
    after_paper_collection_candidate: bool | None = None
    before_reason: str | None = None
    after_reason: str | None = None


class RuntimeAdmissionRefreshReport(BaseModel):
    generated_at: datetime
    applied: bool = False
    apply_allowed: bool = False
    apply_blockers: list[str] = Field(default_factory=list)

    capital_eur: float
    capital_source: str
    active_assets: list[str]
    train_end: datetime
    validation_end: datetime
    evaluated_results: int = Field(ge=0)
    skipped_symbols: dict[str, str] = Field(default_factory=dict)

    drain_enabled: bool
    book_flat: bool
    paper_open_positions: int = Field(ge=0)
    bridge_open_positions: int = Field(ge=0)
    pending_open_command: bool
    pending_close_command: bool

    added: int = Field(ge=0)
    removed: int = Field(ge=0)
    changed: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    changes: list[RuntimeAdmissionRefreshChange] = Field(default_factory=list)

    registry_path: str
    receipt_path: str
