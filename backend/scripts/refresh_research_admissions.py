import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import PortfolioResearchRequest, ResearchSplit
from app.services.opportunity_matrix import run_mt4_portfolio_research
from app.services.research_execution_profile import load_research_execution_profile
from app.services.runtime_admission_registry import save_research_admissions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--timezone", default="Europe/Athens")
    parser.add_argument("--train-end", default="2026-07-01T00:00:00")
    parser.add_argument("--validation-end", default="2026-09-01T00:00:00")
    parser.add_argument(
        "--macro-events",
        type=Path,
        default=Path("config/macro_events_2026.json"),
    )
    parser.add_argument(
        "--execution-profile",
        type=Path,
        default=Path("config/research_execution_profile_2026-09-21.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timezone = ZoneInfo(args.timezone)
    split = ResearchSplit(
        train_end=datetime.fromisoformat(args.train_end).replace(tzinfo=timezone),
        validation_end=datetime.fromisoformat(args.validation_end).replace(
            tzinfo=timezone
        ),
    )
    profile = load_research_execution_profile(args.execution_profile)
    result = run_mt4_portfolio_research(
        args.files_dir,
        PortfolioResearchRequest(split=split),
        macro_events_path=args.macro_events,
        research_execution_profile_path=args.execution_profile,
    )
    path = args.runtime_dir / "strategy_admissions.json"
    save_research_admissions(path, result)
    print(
        f"saved {len(result.results)} research admissions to {path}; "
        f"qualified={result.qualified_strategy_id}; "
        f"execution_profile={profile.version}"
    )


if __name__ == "__main__":
    main()
