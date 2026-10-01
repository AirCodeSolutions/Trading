import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.runtime_admission_refresh import (
    preview_runtime_admissions,
    refresh_runtime_admissions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or explicitly apply the Trading-New runtime admission "
            "refresh using actual MT4 DEMO equity/balance and the frozen split."
        )
    )
    parser.add_argument("--files-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--timezone", default="Europe/Athens")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply the refresh. Fails closed unless drain is ON, "
            "Trading-New BOOK_FLAT is proven and no active symbol was skipped. "
            "Without this flag the command is PREVIEW-only."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(tz=ZoneInfo(args.timezone))
    if args.apply:
        report = refresh_runtime_admissions(
            args.files_dir,
            args.runtime_dir,
            now=now,
        )
    else:
        report = preview_runtime_admissions(
            args.files_dir,
            args.runtime_dir,
            now=now,
        )

    mode = "APPLY" if report.applied else "PREVIEW"
    print(
        f"{mode} runtime admissions; capital={report.capital_eur:.2f} "
        f"source={report.capital_source}; evaluated={report.evaluated_results}; "
        f"added={report.added}; changed={report.changed}; "
        f"removed={report.removed}; unchanged={report.unchanged}; "
        f"apply_allowed={report.apply_allowed}"
    )
    if report.apply_blockers:
        print("blockers=" + " | ".join(report.apply_blockers))
    for change in report.changes:
        if change.change_type.value == "unchanged":
            continue
        print(
            f"{change.strategy_id}: {change.change_type.value} "
            f"{change.before_state or 'none'} -> {change.after_state or 'none'}"
        )


if __name__ == "__main__":
    main()
