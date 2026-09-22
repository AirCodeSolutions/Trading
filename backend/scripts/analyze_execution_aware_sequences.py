from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.execution_aware_sequence_research import (
    build_execution_aware_sequence_report,
)

ATHENS = ZoneInfo("Europe/Athens")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "symbols",
        nargs="*",
        default=list(settings.session_watch_symbols),
    )
    parser.add_argument("--sequence-length", type=int, default=3)
    parser.add_argument("--target-r", type=float, default=1.0)
    args = parser.parse_args()

    report = build_execution_aware_sequence_report(
        Path(settings.mt4_files_dir),
        settings.research_execution_model_path,
        settings.macro_events_path,
        tuple(symbol.upper() for symbol in args.symbols),
        generated_at=datetime.now(ATHENS),
        train_end=datetime(2026, 7, 1, tzinfo=ATHENS),
        validation_end=datetime(2026, 9, 1, tzinfo=ATHENS),
        sequence_length=args.sequence_length,
        target_r=args.target_r,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
