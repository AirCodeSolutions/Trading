from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.authority_regret import (
    AuthorityRegretOpen,
    AuthorityRegretOutcome,
    AuthorityRegretReasonSummary,
    AuthorityRegretRecord,
    AuthorityRegretState,
    AuthorityRegretSummary,
    StrategyAuthorityDecision,
    StrategyAuthoritySnapshot,
)
from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar
from app.domain.portfolio import ProspectiveQualification
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import ShadowPaperSummary
from app.services.admission import demo_collection_allowed
from app.services.prospective_qualification import (
    assess_prospective,
    prospective_demo_execution_allowed,
)
from app.services.shadow_paper import create_paper_trade, resolve_open_trade

RECENT_LIMIT = 25


def _state_path(runtime_dir: Path, prefix: str) -> Path:
    return runtime_dir / f"{prefix}_authority_regret_state.json"


def _records_path(runtime_dir: Path, prefix: str) -> Path:
    return runtime_dir / f"{prefix}_authority_regret.jsonl"


def _load_state(path: Path) -> AuthorityRegretState:
    if not path.is_file():
        return AuthorityRegretState()
    try:
        return AuthorityRegretState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return AuthorityRegretState()


def _save_state(path: Path, state: AuthorityRegretState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
def _append_record(path: Path, record: AuthorityRegretRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json())
        handle.write("\n")


def load_authority_regret_records(path: Path) -> list[AuthorityRegretRecord]:
    if not path.is_file():
        return []
    records: list[AuthorityRegretRecord] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                records.append(AuthorityRegretRecord.model_validate_json(line))
            except ValueError:
                continue
    return records


def _authority_snapshot(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    strategy_id: str,
    admission: AdmissionDecision | None,
    qualification: ProspectiveQualification,
    effective_paper_entry_allowed: bool,
) -> StrategyAuthoritySnapshot:
    historical_demo_allowed = admission is not None and (
        admission.state == AdmissionState.ACTIVE
        or demo_collection_allowed(admission)
    )
    allowed = (
        effective_paper_entry_allowed
        and historical_demo_allowed
        and prospective_demo_execution_allowed(qualification)
    )
    if allowed:
        reason = "historical and prospective evidence support broker DEMO"
    elif admission is None:
        reason = "historical admission unavailable"
    elif admission.state == AdmissionState.REJECTED:
        reason = "historical admission rejected"
    elif not effective_paper_entry_allowed:
        reason = "PAPER evidence gate locked"
    else:
        reason = f"prospective evidence is {qualification.state.value}"
    return StrategyAuthoritySnapshot(
        strategy_id=strategy_id,
        symbol=diagnostic.symbol,
        mechanism=diagnostic.mechanism,
        signal_at=diagnostic.latest_closed_m5_at + timedelta(minutes=5),
        historical_state=admission.state if admission is not None else None,
        prospective_state=qualification.state,
        paper_entry_allowed=effective_paper_entry_allowed,
        decision=(
            StrategyAuthorityDecision.BROKER_DEMO_ALLOWED
            if allowed
            else StrategyAuthorityDecision.BROKER_DEMO_LOCKED
        ),
        reason=reason,
    )
def _classify(
    authority: StrategyAuthoritySnapshot,
    result_r: float,
) -> AuthorityRegretOutcome:
    allowed = authority.decision == StrategyAuthorityDecision.BROKER_DEMO_ALLOWED
    if result_r > 0:
        return (
            AuthorityRegretOutcome.AUTHORIZED_WINNER
            if allowed
            else AuthorityRegretOutcome.LOCKED_WINNER_MISSED
        )
    if result_r < 0:
        return (
            AuthorityRegretOutcome.AUTHORIZED_LOSER
            if allowed
            else AuthorityRegretOutcome.LOCKED_LOSS_AVOIDED
        )
    return AuthorityRegretOutcome.FLAT


def advance_authority_regret_from_paper(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    bars_m5: Sequence[MarketBar],
    runtime_dir: Path,
    prefix: str,
    strategy_id: str,
    admission: AdmissionDecision | None,
    paper_summary: ShadowPaperSummary,
    effective_paper_entry_allowed: bool,
    evaluated_at: datetime,
    allow_new_entries: bool = True,
) -> None:
    advance_authority_regret_book(
        diagnostic=diagnostic,
        spec=spec,
        bars_m5=bars_m5,
        runtime_dir=runtime_dir,
        prefix=prefix,
        strategy_id=strategy_id,
        admission=admission,
        qualification=assess_prospective(strategy_id, paper_summary),
        effective_paper_entry_allowed=effective_paper_entry_allowed,
        evaluated_at=evaluated_at,
        allow_new_entries=allow_new_entries,
    )


def advance_authority_regret_book(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    bars_m5: Sequence[MarketBar],
    runtime_dir: Path,
    prefix: str,
    strategy_id: str,
    admission: AdmissionDecision | None,
    qualification: ProspectiveQualification,
    effective_paper_entry_allowed: bool,
    evaluated_at: datetime,
    allow_new_entries: bool = True,
) -> None:
    state_path = _state_path(runtime_dir, prefix)
    records_path = _records_path(runtime_dir, prefix)
    state = _load_state(state_path)

    remaining: list[AuthorityRegretOpen] = []
    for item in state.open_records:
        resolved = resolve_open_trade(item.trade, bars_m5)
        if resolved.status.value == "open":
            remaining.append(item.model_copy(update={"trade": resolved}))
            continue
        result_r = resolved.result_r or 0.0
        _append_record(
            records_path,
            AuthorityRegretRecord(
                authority=item.authority,
                trade=resolved,
                outcome=_classify(item.authority, result_r),
            ),
        )
    state.open_records = remaining

    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    can_start = (
        allow_new_entries
        and diagnostic.state == ShadowSignalState.SIGNAL_EXECUTABLE
        and diagnostic.side is not None
        and diagnostic.structural_stop is not None
        and diagnostic.base_risk is not None
        and diagnostic.base_risk.approved
        and (
            state.last_started_signal_at is None
            or signal_at > state.last_started_signal_at
        )
    )
    if can_start:
        trade = create_paper_trade(
            diagnostic=diagnostic,
            spec=spec,
            evaluated_at=evaluated_at,
        )
        state.open_records.append(
            AuthorityRegretOpen(
                authority=_authority_snapshot(
                    diagnostic=diagnostic,
                    strategy_id=strategy_id,
                    admission=admission,
                    qualification=qualification,
                    effective_paper_entry_allowed=effective_paper_entry_allowed,
                ),
                trade=trade,
            )
        )
        state.last_started_signal_at = signal_at

    _save_state(state_path, state)
def _reason_summaries(
    records: Sequence[AuthorityRegretRecord],
) -> list[AuthorityRegretReasonSummary]:
    grouped: dict[str, list[AuthorityRegretRecord]] = {}
    for record in records:
        grouped.setdefault(record.authority.reason, []).append(record)
    rows = []
    for reason, items in sorted(grouped.items()):
        results = [item.trade.result_r or 0.0 for item in items]
        rows.append(
            AuthorityRegretReasonSummary(
                reason=reason,
                resolved=len(items),
                total_r=sum(results),
                winners=sum(value > 0 for value in results),
                losers=sum(value < 0 for value in results),
            )
        )
    return rows


def build_authority_regret_summary(
    runtime_dir: Path,
    *,
    now: datetime | None = None,
    window_hours: int | None = None,
) -> AuthorityRegretSummary:
    records = [
        record
        for path in runtime_dir.glob("*_authority_regret.jsonl")
        for record in load_authority_regret_records(path)
    ]
    if now is not None and window_hours is not None:
        lower_bound = now - timedelta(hours=window_hours)
        records = [
            record
            for record in records
            if record.trade.opened_at >= lower_bound
        ]
    records.sort(key=lambda item: (item.trade.opened_at, item.trade.trade_id))
    open_trades = sum(
        len(_load_state(path).open_records)
        for path in runtime_dir.glob("*_authority_regret_state.json")
    )
    authorized = [
        item
        for item in records
        if item.authority.decision
        == StrategyAuthorityDecision.BROKER_DEMO_ALLOWED
    ]
    locked = [
        item
        for item in records
        if item.authority.decision
        == StrategyAuthorityDecision.BROKER_DEMO_LOCKED
    ]
    missed_winner_r = sum(
        item.trade.result_r or 0.0
        for item in locked
        if (item.trade.result_r or 0.0) > 0
    )
    avoided_loss_r = -sum(
        item.trade.result_r or 0.0
        for item in locked
        if (item.trade.result_r or 0.0) < 0
    )
    return AuthorityRegretSummary(
        resolved=len(records),
        open_trades=open_trades,
        authorized_winners=sum(
            item.outcome == AuthorityRegretOutcome.AUTHORIZED_WINNER
            for item in records
        ),
        authorized_losers=sum(
            item.outcome == AuthorityRegretOutcome.AUTHORIZED_LOSER
            for item in records
        ),
        locked_winners_missed=sum(
            item.outcome == AuthorityRegretOutcome.LOCKED_WINNER_MISSED
            for item in records
        ),
        locked_losses_avoided=sum(
            item.outcome == AuthorityRegretOutcome.LOCKED_LOSS_AVOIDED
            for item in records
        ),
        authorized_total_r=sum(item.trade.result_r or 0.0 for item in authorized),
        locked_counterfactual_total_r=sum(
            item.trade.result_r or 0.0 for item in locked
        ),
        missed_winner_r=missed_winner_r,
        avoided_loss_r=avoided_loss_r,
        net_authority_regret_r=missed_winner_r - avoided_loss_r,
        by_reason=_reason_summaries(records),
        recent=records[-RECENT_LIMIT:][::-1],
        broker_authority_changed=False,
    )
