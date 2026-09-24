import fcntl
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from app.core.config import settings
from app.services.mt4_csv import _server_timezone
from app.services.xau_microbar import sample_xau_microbar_once

SAMPLE_INTERVAL_SECONDS = 1.0
HEARTBEAT_FILE = "XAUUSD_micro_m1_heartbeat.json"
LOCK_FILE = "xau-microbar-worker.lock"


def main() -> None:
    if settings.mt4_files_dir is None:
        raise SystemExit("TRADING_MT4_FILES_DIR is required")

    _worker_lock = _acquire_worker_lock(
        settings.shadow_ledger_dir / LOCK_FILE
    )
    heartbeat_path = settings.shadow_ledger_dir / HEARTBEAT_FILE

    while True:
        now = datetime.now(tz=_server_timezone())
        try:
            summary = sample_xau_microbar_once(
                settings.mt4_files_dir,
                settings.shadow_ledger_dir,
                now,
            )
            _write_heartbeat(
                heartbeat_path,
                {
                    "at": now.isoformat(),
                    "ok": True,
                    "healthy": summary.healthy,
                    "last_quote_at": (
                        summary.last_quote_at.isoformat()
                        if summary.last_quote_at is not None
                        else None
                    ),
                    "quote_age_seconds": summary.quote_age_seconds,
                    "total_quote_samples": summary.total_quote_samples,
                    "closed_bars": summary.closed_bars,
                    "error": None,
                },
            )
        except (OSError, TypeError, ValueError) as exc:
            _write_heartbeat(
                heartbeat_path,
                {
                    "at": now.isoformat(),
                    "ok": False,
                    "healthy": False,
                    "last_quote_at": None,
                    "quote_age_seconds": None,
                    "total_quote_samples": 0,
                    "closed_bars": 0,
                    "error": repr(exc),
                },
            )
        time.sleep(SAMPLE_INTERVAL_SECONDS)


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
        raise SystemExit("XAU microbar worker already running") from exc

    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def _write_heartbeat(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
