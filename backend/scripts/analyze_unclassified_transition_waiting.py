from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.unclassified_transition_research import (
    analyze_unclassified_transition_waiting,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "symbols",
        nargs="*",
        default=list(settings.session_watch_symbols),
    )
    parser.add_argument("--capital-eur", type=float, required=True)
    parser.add_argument("--max-wait-bars", type=int, default=3)
    args = parser.parse_args()

    timezone = ZoneInfo(settings.mt4_server_timezone)
    payload = analyze_unclassified_transition_waiting(
        Path(settings.mt4_files_dir),
        settings.research_execution_model_path,
        settings.macro_events_path,
        tuple(symbol.upper() for symbol in args.symbols),
        train_end=datetime(2026, 7, 1, tzinfo=timezone),
        validation_end=datetime(2026, 9, 1, tzinfo=timezone),
        capital_eur=args.capital_eur,
        max_wait_bars=args.max_wait_bars,
    )
    payload["generated_at"] = datetime.now(timezone).isoformat()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
