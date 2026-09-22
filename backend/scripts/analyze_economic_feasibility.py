from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.economic_feasibility import (
    build_economic_feasibility_report,
    write_economic_feasibility_report,
)

ATHENS = ZoneInfo("Europe/Athens")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "symbols",
        nargs="*",
        default=list(settings.session_watch_symbols),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON snapshot path. Stdout is always emitted.",
    )
    args = parser.parse_args()

    report = build_economic_feasibility_report(
        Path(settings.mt4_files_dir),
        Path("config/research_execution_model.json"),
        tuple(symbol.upper() for symbol in args.symbols),
        generated_at=datetime.now(ATHENS),
    )
    if args.output is not None:
        write_economic_feasibility_report(args.output, report)
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
