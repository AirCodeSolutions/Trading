from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.market_first_signatures import analyze_market_first_signatures

ATHENS = ZoneInfo("Europe/Athens")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+")
    args = parser.parse_args()

    files_dir = Path(settings.mt4_files_dir)
    train_end = datetime(2026, 7, 1, tzinfo=ATHENS)
    validation_end = datetime(2026, 9, 1, tzinfo=ATHENS)

    payload = [
        analyze_market_first_signatures(
            files_dir,
            symbol.upper(),
            train_end=train_end,
            validation_end=validation_end,
        )
        for symbol in args.symbols
    ]
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
