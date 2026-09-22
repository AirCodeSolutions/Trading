from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.causal_economic_matrix import build_causal_economic_matrix

ATHENS = ZoneInfo("Europe/Athens")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "symbols",
        nargs="*",
        default=list(settings.session_watch_symbols),
    )
    args = parser.parse_args()

    report = build_causal_economic_matrix(
        Path(settings.mt4_files_dir),
        settings.research_execution_model_path,
        tuple(symbol.upper() for symbol in args.symbols),
        generated_at=datetime.now(ATHENS),
        train_end=datetime(2026, 7, 1, tzinfo=ATHENS),
        validation_end=datetime(2026, 9, 1, tzinfo=ATHENS),
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
