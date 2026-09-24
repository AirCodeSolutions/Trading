import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import (
    OpportunityMechanism,
    PortfolioResearchRequest,
    ResearchSplit,
)
from app.services.opportunity_matrix import run_mt4_portfolio_research
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
        "--research-execution-model",
        type=Path,
        default=Path("config/research_execution_model.json"),
    )
    parser.add_argument(
        "--capital-eur",
        type=float,
        default=None,
        help="Explicit research sizing capital; defaults to configured fallback.",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
        help="Limit refresh to one symbol; repeat for multiple symbols.",
    )
    parser.add_argument(
        "--mechanism",
        action="append",
        type=OpportunityMechanism,
        dest="mechanisms",
        help="Limit refresh to one mechanism; repeat for multiple mechanisms.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge refreshed admissions into the existing registry.",
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
    request_kwargs: dict[str, object] = {
        "split": split,
        "capital_eur": args.capital_eur,
    }
    if args.symbols:
        request_kwargs["symbols"] = args.symbols
    if args.mechanisms:
        request_kwargs["mechanisms"] = args.mechanisms

    result = run_mt4_portfolio_research(
        args.files_dir,
        PortfolioResearchRequest.model_validate(request_kwargs),
        macro_events_path=args.macro_events,
        research_execution_model_path=args.research_execution_model,
    )
    path = args.runtime_dir / "strategy_admissions.json"
    save_research_admissions(path, result, merge=args.merge)
    print(
        f"saved {len(result.results)} research admissions to {path}; "
        f"qualified={result.qualified_strategy_id}"
    )


if __name__ == "__main__":
    main()
