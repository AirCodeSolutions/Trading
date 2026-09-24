import fcntl
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

from app.core.config import settings
from app.domain.portfolio import TradingOverview
from app.domain.session import ShadowWorkerHeartbeat
from app.domain.shadow import ShadowCollectionResult
from app.services.causal_precursor import advance_causal_precursors_once
from app.services.daily_report import (
    build_daily_trading_report,
    write_daily_trading_report,
)
from app.services.demo_collection import advance_demo_collection
from app.services.demo_execution import RESULT_FILE, read_demo_result
from app.services.execution_audit import (
    AUDIT_FILE,
    append_bridge_result_if_new,
)
from app.services.execution_cost_history import collect_execution_cost_snapshot
from app.services.macro_gate import macro_gate_status
from app.services.mt4_csv import _server_timezone
from app.services.multi_shadow_collector import collect_all_shadow_once
from app.services.portfolio_overview import build_trading_overview
from app.services.qualification_history import record_qualification_history
from app.services.runtime_control import DRAIN_FILE, load_runtime_drain
from app.services.trading_intelligence import (
    INTELLIGENCE_FILE,
    build_trading_intelligence,
    write_trading_intelligence,
)
from app.services.trailing_shadow import advance_trailing_shadow_once
from app.services.xau_auction_precursor_shadow import (
    advance_xau_auction_precursor_shadow_once,
)
from app.services.xau_compression_precursor_shadow import (
    advance_xau_compression_precursor_shadow_once,
)
from app.services.xau_feasible_pullback_shadow import (
    advance_xau_feasible_pullback_shadow_once,
)
from app.services.xau_unseen_transition_capture import (
    capture_unseen_transition_snapshots,
)


def main() -> None:
    if settings.mt4_files_dir is None:
        raise SystemExit("TRADING_MT4_FILES_DIR is required")

    _worker_lock = _acquire_worker_lock(
        settings.shadow_ledger_dir / "worker.lock"
    )
    costs_path = settings.shadow_ledger_dir / "execution_costs.jsonl"
    heartbeat_path = settings.shadow_ledger_dir / "worker_heartbeat.json"
    audit_path = settings.shadow_ledger_dir / AUDIT_FILE
    qualification_path = settings.shadow_ledger_dir / "qualification_history.jsonl"
    intelligence_path = settings.shadow_ledger_dir / INTELLIGENCE_FILE
    while True:
        now = datetime.now(tz=_server_timezone())
        try:
            cost_samples = collect_execution_cost_snapshot(
                settings.mt4_files_dir,
                costs_path,
                now,
                symbols=settings.session_watch_symbols,
            )
            drain = load_runtime_drain(settings.shadow_ledger_dir / DRAIN_FILE)
            results = collect_all_shadow_once(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now,
                allow_paper_entries=not drain.enabled,
            )
            overview = build_trading_overview(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now,
            )
            macro = macro_gate_status(settings.macro_events_path, now)
            if settings.demo_collection_enabled:
                advance_demo_collection(
                    settings.mt4_files_dir,
                    settings.shadow_ledger_dir,
                    overview,
                    macro,
                    now,
                    allow_new_entries=not drain.enabled,
                )
            observability_errors = _update_observability(
                audit_path=audit_path,
                qualification_path=qualification_path,
                intelligence_path=intelligence_path,
                overview=overview,
                results=results,
                now=now,
            )
            if observability_errors:
                print(
                    json.dumps(
                        {"shadow_worker_observability_errors": observability_errors}
                    ),
                    flush=True,
                )
            signals = sum(
                item.diagnostic.state != "no_signal"
                for item in results
            )
            paper_ready_symbols = sorted(
                {item.diagnostic.symbol for item in results}
            )
            warming_up_symbols = sorted(
                {
                    item.diagnostic.symbol
                    for item in results
                    if item.diagnostic.reason.startswith(
                        "session reopen warmup:"
                    )
                }
            )
            heartbeat = ShadowWorkerHeartbeat(
                at=now,
                ok=True,
                cost_samples_appended=cost_samples,
                shadow_scans=len(results),
                signals=signals,
                paper_ready_symbols=paper_ready_symbols,
                warming_up_symbols=warming_up_symbols,
            )
            _write_heartbeat(heartbeat_path, heartbeat)
            print(heartbeat.model_dump_json(), flush=True)
        except (OSError, TypeError, ValueError) as exc:
            heartbeat = ShadowWorkerHeartbeat(
                at=now,
                ok=False,
                cost_samples_appended=0,
                shadow_scans=0,
                signals=0,
                paper_ready_symbols=[],
                warming_up_symbols=[],
                error=repr(exc),
            )
            _write_heartbeat(heartbeat_path, heartbeat)
            print(
                json.dumps({"shadow_worker_error": repr(exc)}),
                flush=True,
            )
        time.sleep(settings.shadow_collection_interval_seconds)


def _acquire_worker_lock(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
    except BlockingIOError as exc:
        handle.close()
        raise SystemExit("shadow worker already running") from exc

    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def _update_observability(
    *,
    audit_path: Path,
    qualification_path: Path,
    intelligence_path: Path,
    overview: TradingOverview,
    results: list[ShadowCollectionResult] | None = None,
    now: datetime,
) -> list[str]:
    errors: list[str] = []

    try:
        advance_causal_precursors_once(
            settings.mt4_files_dir,
            settings.shadow_ledger_dir,
            now,
            symbols=settings.session_watch_symbols,
        )
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"causal_precursor: {exc!r}")

    try:
        advance_trailing_shadow_once(
            settings.mt4_files_dir,
            settings.shadow_ledger_dir,
            now,
        )
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"trailing_shadow: {exc!r}")

    asia_diagnostic = next(
        (
            item.diagnostic
            for item in (results or [])
            if item.diagnostic.symbol.upper() == "XAUUSD"
            and item.diagnostic.mechanism.value == "asia_range_sweep_reversal"
        ),
        None,
    )
    if asia_diagnostic is not None:
        try:
            advance_xau_feasible_pullback_shadow_once(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                asia_diagnostic,
                now,
            )
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"xau_feasible_pullback_shadow: {exc!r}")

    try:
        append_bridge_result_if_new(
            audit_path,
            read_demo_result(settings.mt4_files_dir / RESULT_FILE),
            at=now,
        )
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"execution_audit: {exc!r}")

    try:
        record_qualification_history(
            qualification_path,
            overview,
            at=now,
        )
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"qualification_history: {exc!r}")

    if _snapshot_due(intelligence_path):
        try:
            intelligence = build_trading_intelligence(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now=now,
                window_hours=24,
                symbols=settings.session_watch_symbols,
            )
            write_trading_intelligence(intelligence_path, intelligence)
            try:
                capture_unseen_transition_snapshots(
                    settings.mt4_files_dir,
                    settings.shadow_ledger_dir,
                    intelligence,
                    now=now,
                    symbols=settings.session_watch_symbols,
                )
            except (OSError, TypeError, ValueError) as exc:
                errors.append(f"market_unseen_m1_transition: {exc!r}")
            try:
                advance_xau_compression_precursor_shadow_once(
                    settings.mt4_files_dir,
                    settings.shadow_ledger_dir,
                    now,
                )
            except (OSError, TypeError, ValueError) as exc:
                errors.append(f"xau_compression_precursor_shadow: {exc!r}")
            try:
                advance_xau_auction_precursor_shadow_once(
                    settings.mt4_files_dir,
                    settings.shadow_ledger_dir,
                    now,
                )
            except (OSError, TypeError, ValueError) as exc:
                errors.append(f"xau_auction_precursor_shadow: {exc!r}")
            report = build_daily_trading_report(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now=now,
                overview=overview,
                intelligence=intelligence,
            )
            write_daily_trading_report(settings.shadow_ledger_dir, report)
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"intelligence_snapshot: {exc!r}")

    return errors


def _write_heartbeat(
    path: Path,
    heartbeat: ShadowWorkerHeartbeat,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        heartbeat.model_dump_json(indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _snapshot_due(path: Path, max_age_seconds: float = 300.0) -> bool:
    if not path.is_file():
        return True
    try:
        return time.time() - path.stat().st_mtime >= max_age_seconds
    except OSError:
        return True


if __name__ == "__main__":
    main()
