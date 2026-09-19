import time
from datetime import datetime

from app.core.config import settings
from app.services.mt4_csv import _server_timezone
from app.services.shadow_collector import collect_btc_break_retest_once


def main() -> None:
    if settings.mt4_files_dir is None:
        raise SystemExit("TRADING_MT4_FILES_DIR is required")

    ledger_path = settings.shadow_ledger_dir / "BTCUSD_break_retest.jsonl"
    while True:
        try:
            result = collect_btc_break_retest_once(
                settings.mt4_files_dir,
                ledger_path,
                datetime.now(tz=_server_timezone()),
            )
            print(result.model_dump_json(), flush=True)
        except Exception as exc:
            print(f'{{"shadow_worker_error": {exc!r}}}', flush=True)
        time.sleep(settings.shadow_collection_interval_seconds)


if __name__ == "__main__":
    main()
