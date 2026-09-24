from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.macro import MacroSignalPhase
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityMechanism,
    ResearchSplit,
    TradeOutcome,
)
from app.services.macro_gate import (
    active_macro_blackouts,
    classify_macro_signal_context,
    load_macro_events,
)
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import _simulate_candidate, _summary
from app.services.opportunity_strategies import generate_candidates
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)

DEFAULT_POST_SAFE_WINDOW_MINUTES = 135


def _split_summary(
    outcomes: list[TradeOutcome],
    split: ResearchSplit,
) -> dict[str, object]:
    return {
        "train": _summary(
            [row for row in outcomes if row.signal_at < split.train_end]
        ).model_dump(mode="json"),
        "validation": _summary(
            [
                row
                for row in outcomes
                if split.train_end <= row.signal_at < split.validation_end
            ]
        ).model_dump(mode="json"),
        "holdout": _summary(
            [
                row
                for row in outcomes
                if row.signal_at >= split.validation_end
            ]
        ).model_dump(mode="json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "symbols",
        nargs="*",
        default=list(settings.session_watch_symbols),
    )
    parser.add_argument("--capital-eur", type=float, default=None)
    parser.add_argument(
        "--post-safe-window-minutes",
        type=int,
        default=DEFAULT_POST_SAFE_WINDOW_MINUTES,
    )
    args = parser.parse_args()

    if args.post_safe_window_minutes < 0:
        raise SystemExit("--post-safe-window-minutes must be non-negative")

    tz = ZoneInfo(settings.mt4_server_timezone)
    split = ResearchSplit(
        train_end=datetime(2026, 7, 1, tzinfo=tz),
        validation_end=datetime(2026, 9, 1, tzinfo=tz),
    )
    capital_eur = args.capital_eur or settings.reference_capital_eur
    events = load_macro_events(settings.macro_events_path)
    specs = list_mt4_symbol_specs(Path(settings.mt4_files_dir))
    execution_model = load_research_execution_model(
        settings.research_execution_model_path
    )

    rows: list[dict[str, object]] = []
    for raw_symbol in args.symbols:
        symbol = raw_symbol.upper()
        spec = specs.get(symbol)
        if spec is None:
            continue
        spec = apply_research_execution_model(spec, execution_model)
        m5 = read_mt4_csv(
            resolve_mt4_history_path(
                Path(settings.mt4_files_dir),
                symbol,
                Timeframe.M5,
            ),
            symbol,
            Timeframe.M5,
        )
        m15 = read_mt4_csv(
            resolve_mt4_history_path(
                Path(settings.mt4_files_dir),
                symbol,
                Timeframe.M15,
            ),
            symbol,
            Timeframe.M15,
        )

        for mechanism in OpportunityMechanism:
            if (
                mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
                and symbol not in {"BTCUSD", "XAUUSD"}
            ):
                continue
            if (
                mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE
                and symbol != "XAUUSD"
            ):
                continue

            config = OpportunityBacktestConfig(
                spec=spec,
                mechanism=mechanism,
                split=split,
                capital_eur=capital_eur,
                macro_events=events,
            )
            outcomes: list[TradeOutcome] = []
            busy_until = -1
            for candidate in generate_candidates(m5, m15, mechanism):
                if candidate.entry_index <= busy_until:
                    continue
                if active_macro_blackouts(events, candidate.entry_at):
                    continue
                outcome, exit_index, rejection = _simulate_candidate(
                    m5,
                    candidate,
                    config,
                )
                if (
                    rejection is not None
                    or outcome is None
                    or exit_index is None
                ):
                    continue
                outcomes.append(outcome)
                busy_until = exit_index

            if not outcomes:
                continue

            post_safe = [
                row
                for row in outcomes
                if classify_macro_signal_context(
                    events,
                    row.entry_at,
                    post_safe_window_minutes=args.post_safe_window_minutes,
                ).phase
                == MacroSignalPhase.POST_SAFE
            ]
            normal = [
                row
                for row in outcomes
                if classify_macro_signal_context(
                    events,
                    row.entry_at,
                    post_safe_window_minutes=args.post_safe_window_minutes,
                ).phase
                == MacroSignalPhase.NORMAL
            ]
            if not post_safe:
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "mechanism": mechanism.value,
                    "post_safe": _summary(post_safe).model_dump(mode="json"),
                    "normal": _summary(normal).model_dump(mode="json"),
                    "post_safe_splits": _split_summary(post_safe, split),
                }
            )

    payload = {
        "generated_at": datetime.now(tz).isoformat(),
        "reference_capital_eur": capital_eur,
        "post_safe_window_minutes": args.post_safe_window_minutes,
        "rows": rows,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
