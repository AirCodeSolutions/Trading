import argparse
from pathlib import Path

from app.services.macro_sync import sync_bls_calendar


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("config/macro_events_2026.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    args = parser.parse_args()
    count = sync_bls_calendar(args.base, args.output)
    print(f"synced {count} BLS macro events to {args.output}")


if __name__ == "__main__":
    main()
