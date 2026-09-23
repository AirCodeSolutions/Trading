import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityMechanism,
    ResearchSplit,
)
from app.domain.trailing_manager import TrailingManagerConfig
from app.services.macro_gate import load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.trailing_research import run_trailing_manager_research


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument(
        "--mechanism",
        type=OpportunityMechanism,
        default=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    )
    parser.add_argument(
        "--mode",
        choices=(
            "stop-only",
            "target-only",
            "stop-plus-target",
            "target-plus-protection",
        ),
        default="stop-only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = args.symbol.upper()
    files_dir = Path(settings.mt4_files_dir)
    specs = list_mt4_symbol_specs(files_dir)
    spec = specs[symbol]
    spec = apply_research_execution_model(
        spec,
        load_research_execution_model(settings.research_execution_model_path),
    )
    m5_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M5)
    m15_path = resolve_mt4_history_path(files_dir, symbol, Timeframe.M15)
    if m5_path is None or m15_path is None:
        raise SystemExit("M5/M15 history unavailable")

    bars_m5 = read_mt4_csv(m5_path, symbol, Timeframe.M5)
    bars_m15 = read_mt4_csv(m15_path, symbol, Timeframe.M15)
    athens = ZoneInfo("Europe/Athens")
    backtest = OpportunityBacktestConfig(
        spec=spec,
        mechanism=args.mechanism,
        split=ResearchSplit(
            train_end=datetime(2026, 7, 1, tzinfo=athens),
            validation_end=datetime(2026, 9, 1, tzinfo=athens),
        ),
        macro_events=load_macro_events(settings.macro_events_path),
    )
    policy = TrailingManagerConfig(
        enable_stop_trailing=args.mode in {
            "stop-only",
            "stop-plus-target",
            "target-plus-protection",
        },
        enable_target_extension=args.mode in {
            "target-only",
            "stop-plus-target",
            "target-plus-protection",
        },
        target_extension_requires_protected_stop=(
            args.mode == "stop-plus-target"
        ),
        stop_trailing_requires_extended_target=(
            args.mode == "target-plus-protection"
        ),
    )
    report = run_trailing_manager_research(
        bars_m5,
        bars_m15,
        backtest,
        policy=policy,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
