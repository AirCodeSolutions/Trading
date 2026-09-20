import json
import time
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.domain.session import ShadowWorkerHeartbeat
from app.services.execution_cost_history import collect_execution_cost_snapshot
from app.services.mt4_csv import _server_timezone
from app.services.multi_shadow_collector import collect_all_shadow_once


def main() -> None:
    if settings.mt4_files_dir is None:
        raise SystemExit("TRADING_MT4_FILES_DIR is required")

    costs_path = settings.shadow_ledger_dir / "execution_costs.jsonl"
    heartbeat_path = settings.shadow_ledger_dir / "worker_heartbeat.json"
    while True:
        now = datetime.now(tz=_server_timezone())
        try:
            cost_samples = collect_execution_cost_snapshot(
                settings.mt4_files_dir,
                costs_path,
                now,
            )
            results = collect_all_shadow_once(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now,
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


if __name__ == "__main__":
    main()
