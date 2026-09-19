import json
import time
from datetime import datetime

from app.core.config import settings
from app.services.execution_cost_history import collect_execution_cost_snapshot
from app.services.mt4_csv import _server_timezone
from app.services.multi_shadow_collector import collect_all_shadow_once


def main() -> None:
    if settings.mt4_files_dir is None:
        raise SystemExit("TRADING_MT4_FILES_DIR is required")

    costs_path = settings.shadow_ledger_dir / "execution_costs.jsonl"
    while True:
        try:
            now = datetime.now(tz=_server_timezone())
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
            print(
                json.dumps(
                    {
                        "at": now.isoformat(),
                        "cost_samples_appended": cost_samples,
                        "shadow_scans": len(results),
                        "signals": sum(
                            item.diagnostic.state != "no_signal"
                            for item in results
                        ),
                    }
                ),
                flush=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            print(json.dumps({"shadow_worker_error": repr(exc)}), flush=True)
        time.sleep(settings.shadow_collection_interval_seconds)


if __name__ == "__main__":
    main()
