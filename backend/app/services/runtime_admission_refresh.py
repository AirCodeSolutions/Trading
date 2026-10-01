from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.domain.admission import AdmissionDecision
from app.domain.opportunity import PortfolioResearchRequest, PortfolioResearchResult
from app.domain.runtime_admission_refresh import (
    AdmissionRefreshChangeType,
    RuntimeAdmissionRefreshChange,
    RuntimeAdmissionRefreshReport,
)
from app.domain.strategy_universe import ACTIVE_ASSETS
from app.services.demo_execution import (
    CLOSE_COMMAND_FILE,
    COMMAND_FILE,
    POSITIONS_FILE,
    read_demo_positions,
    read_pending_close_command,
    read_pending_command,
)
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.paper_registry import load_paper_registry
from app.services.probe_review import default_probe_review_split
from app.services.runtime_admission_registry import (
    load_research_admissions,
    save_research_admissions,
)
from app.services.runtime_capital import resolve_demo_sizing_capital
from app.services.runtime_control import DRAIN_FILE, load_runtime_drain

RECEIPT_FILE = "runtime_admission_refresh_receipt.json"
REGISTRY_FILE = "strategy_admissions.json"


def _evaluate_runtime_admissions(
    files_dir: Path,
) -> tuple[object, PortfolioResearchResult]:
    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or not capital.is_demo:
        raise ValueError(
            "runtime admission refresh requires available MT4 DEMO equity/balance"
        )

    request = PortfolioResearchRequest(
        split=default_probe_review_split(),
        symbols=list(ACTIVE_ASSETS),
        capital_eur=capital.capital_eur,
        requested_risk_fraction=settings.risk_per_trade_fraction,
    )
    result = run_mt4_portfolio_research(
        files_dir,
        request,
        macro_events_path=settings.macro_events_path,
        research_execution_model_path=settings.research_execution_model_path,
    )
    return capital, result


def _decision_map(
    result: PortfolioResearchResult,
) -> dict[str, AdmissionDecision]:
    return {
        item.admission.strategy_id: item.admission
        for item in result.results
    }
def _change(
    strategy_id: str,
    before: AdmissionDecision | None,
    after: AdmissionDecision | None,
) -> RuntimeAdmissionRefreshChange:
    if before is None:
        change_type = AdmissionRefreshChangeType.ADDED
    elif after is None:
        change_type = AdmissionRefreshChangeType.REMOVED
    elif before.model_dump() == after.model_dump():
        change_type = AdmissionRefreshChangeType.UNCHANGED
    else:
        change_type = AdmissionRefreshChangeType.CHANGED

    return RuntimeAdmissionRefreshChange(
        strategy_id=strategy_id,
        change_type=change_type,
        before_state=before.state.value if before is not None else None,
        after_state=after.state.value if after is not None else None,
        before_weakest_expectancy_r=(
            before.weakest_expectancy_r if before is not None else None
        ),
        after_weakest_expectancy_r=(
            after.weakest_expectancy_r if after is not None else None
        ),
        before_worst_drawdown_r=(
            before.worst_drawdown_r if before is not None else None
        ),
        after_worst_drawdown_r=(
            after.worst_drawdown_r if after is not None else None
        ),
        before_paper_collection_candidate=(
            before.paper_collection_candidate if before is not None else None
        ),
        after_paper_collection_candidate=(
            after.paper_collection_candidate if after is not None else None
        ),
        before_reason=before.reason if before is not None else None,
        after_reason=after.reason if after is not None else None,
    )


def _operational_state(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
) -> dict[str, object]:
    drain = load_runtime_drain(runtime_dir / DRAIN_FILE)
    bridge_positions = read_demo_positions(files_dir / POSITIONS_FILE)
    pending_open = read_pending_command(files_dir / COMMAND_FILE)
    pending_close = read_pending_close_command(files_dir / CLOSE_COMMAND_FILE)
    paper_rows = load_paper_registry(
        runtime_dir,
        now,
        settings.paper_evidence_cutover_at,
    )
    paper_open = sum(
        row.summary.open_trade is not None
        for row in paper_rows
    )
    book_flat = (
        paper_open == 0
        and len(bridge_positions) == 0
        and pending_open is None
        and pending_close is None
    )
    return {
        "drain_enabled": drain.enabled,
        "paper_open_positions": paper_open,
        "bridge_open_positions": len(bridge_positions),
        "pending_open_command": pending_open is not None,
        "pending_close_command": pending_close is not None,
        "book_flat": book_flat,
    }
def _build_report(
    *,
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
    capital,
    result: PortfolioResearchResult,
    applied: bool,
) -> RuntimeAdmissionRefreshReport:
    registry_path = runtime_dir / REGISTRY_FILE
    receipt_path = runtime_dir / RECEIPT_FILE
    before = load_research_admissions(registry_path)
    after = _decision_map(result)
    strategy_ids = sorted(set(before) | set(after))
    changes = [
        _change(strategy_id, before.get(strategy_id), after.get(strategy_id))
        for strategy_id in strategy_ids
    ]
    operational = _operational_state(
        files_dir,
        runtime_dir,
        now=now,
    )
    blockers: list[str] = []
    if not operational["drain_enabled"]:
        blockers.append("runtime drain must be ON")
    if not operational["book_flat"]:
        blockers.append("Trading-New book must be flat")
    if result.skipped_symbols:
        blockers.append(
            "research skipped symbols: "
            + ", ".join(sorted(result.skipped_symbols))
        )

    split = default_probe_review_split()
    return RuntimeAdmissionRefreshReport(
        generated_at=now,
        applied=applied,
        apply_allowed=not blockers,
        apply_blockers=blockers,
        capital_eur=capital.capital_eur,
        capital_source=capital.source.value,
        active_assets=list(ACTIVE_ASSETS),
        train_end=split.train_end,
        validation_end=split.validation_end,
        evaluated_results=len(result.results),
        skipped_symbols=dict(result.skipped_symbols),
        drain_enabled=bool(operational["drain_enabled"]),
        book_flat=bool(operational["book_flat"]),
        paper_open_positions=int(operational["paper_open_positions"]),
        bridge_open_positions=int(operational["bridge_open_positions"]),
        pending_open_command=bool(operational["pending_open_command"]),
        pending_close_command=bool(operational["pending_close_command"]),
        added=sum(
            row.change_type == AdmissionRefreshChangeType.ADDED
            for row in changes
        ),
        removed=sum(
            row.change_type == AdmissionRefreshChangeType.REMOVED
            for row in changes
        ),
        changed=sum(
            row.change_type == AdmissionRefreshChangeType.CHANGED
            for row in changes
        ),
        unchanged=sum(
            row.change_type == AdmissionRefreshChangeType.UNCHANGED
            for row in changes
        ),
        changes=changes,
        registry_path=str(registry_path),
        receipt_path=str(receipt_path),
    )


def _save_receipt(path: Path, report: RuntimeAdmissionRefreshReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
def preview_runtime_admissions(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
) -> RuntimeAdmissionRefreshReport:
    capital, result = _evaluate_runtime_admissions(files_dir)
    return _build_report(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=now,
        capital=capital,
        result=result,
        applied=False,
    )


def refresh_runtime_admissions(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
) -> RuntimeAdmissionRefreshReport:
    capital, result = _evaluate_runtime_admissions(files_dir)
    preview = _build_report(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=now,
        capital=capital,
        result=result,
        applied=False,
    )
    if not preview.apply_allowed:
        raise ValueError(
            "runtime admission refresh apply blocked: "
            + "; ".join(preview.apply_blockers)
        )

    save_research_admissions(
        runtime_dir / REGISTRY_FILE,
        result,
    )
    applied = preview.model_copy(update={"applied": True})
    _save_receipt(runtime_dir / RECEIPT_FILE, applied)
    return applied
