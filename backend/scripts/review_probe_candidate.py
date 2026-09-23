import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.opportunity import ResearchSplit
from app.services.probe_review import build_probe_review_pack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a read-only dedicated review pack for a SUPPORTS_REVIEW probe family."
    )
    parser.add_argument("strategy_id", help="SYMBOL:mechanism")
    parser.add_argument("--files-dir", type=Path, default=settings.mt4_files_dir)
    parser.add_argument("--runtime-dir", type=Path, default=settings.shadow_ledger_dir)
    parser.add_argument("--macro-events", type=Path, default=settings.macro_events_path)
    parser.add_argument(
        "--execution-model",
        type=Path,
        default=settings.research_execution_model_path,
    )
    parser.add_argument("--train-end", default="2026-07-01T00:00:00")
    parser.add_argument("--validation-end", default="2026-09-01T00:00:00")
    parser.add_argument("--timezone", default="Europe/Athens")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.files_dir is None:
        raise SystemExit("--files-dir is required")
    timezone = ZoneInfo(args.timezone)
    now = datetime.now(tz=timezone)
    split = ResearchSplit(
        train_end=datetime.fromisoformat(args.train_end).replace(tzinfo=timezone),
        validation_end=datetime.fromisoformat(args.validation_end).replace(tzinfo=timezone),
    )
    pack = build_probe_review_pack(
        args.files_dir,
        args.runtime_dir,
        strategy_id=args.strategy_id,
        now=now,
        split=split,
        macro_events_path=args.macro_events,
        research_execution_model_path=args.execution_model,
    )
    print(pack.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
