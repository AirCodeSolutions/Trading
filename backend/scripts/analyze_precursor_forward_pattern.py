import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.precursor_forward_research import (
    _independent_outcomes,
    _resolve_symbol_outcomes,
)
from app.services.trading_intelligence import _atr_series, _classify_causal_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pattern",
        type=OpportunityCausalPattern,
        default=OpportunityCausalPattern.COMPRESSION_BREAKOUT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tz = ZoneInfo(settings.mt4_server_timezone)
    train_end = datetime(2026, 7, 1, tzinfo=tz)
    validation_end = datetime(2026, 9, 1, tzinfo=tz)

    all_outcomes = []
    for symbol in settings.session_watch_symbols:
        path = resolve_mt4_history_path(
            Path(settings.mt4_files_dir),
            symbol,
            Timeframe.M5,
        )
        if path is None:
            continue
        bars = read_mt4_csv(path, symbol, Timeframe.M5)
        atr = _atr_series(bars)
        observations = []
        for index in range(24, max(24, len(bars) - 12)):
            context = _classify_causal_context(
                bars=bars,
                atr=atr,
                index=index,
                episode_side=Side.BUY,
            ).model_copy(update={"aligned_with_move": None})
            if context.pattern != args.pattern or context.side is None:
                continue
            observations.append(
                CausalPrecursorObservation(
                    symbol=symbol,
                    first_seen_at=bars[index].timestamp + timedelta(minutes=5),
                    latest_closed_m5_at=bars[index].timestamp,
                    pattern=context.pattern,
                    side=context.side,
                    context=context,
                )
            )
        resolved, _ = _resolve_symbol_outcomes(
            observations,
            bars,
            horizon_bars=12,
        )
        all_outcomes.extend(
            _independent_outcomes(resolved, horizon_bars=12)
        )

    splits = {
        "train": [x for x in all_outcomes if x.first_seen_at < train_end],
        "validation": [
            x
            for x in all_outcomes
            if train_end <= x.first_seen_at < validation_end
        ],
        "holdout": [
            x for x in all_outcomes if x.first_seen_at >= validation_end
        ],
    }
    print("pattern", args.pattern.value)
    print("independent_total", len(all_outcomes))
    for name, rows in splits.items():
        print(name, _summary(rows))

    by_symbol = defaultdict(list)
    for row in all_outcomes:
        by_symbol[row.symbol].append(row)
    for symbol in sorted(by_symbol):
        print("symbol", symbol, _summary(by_symbol[symbol]))


def _summary(rows):
    if not rows:
        return {
            "n": 0,
            "mfe_atr": 0.0,
            "mae_atr": 0.0,
            "close_return_atr": 0.0,
            "favorable_dominance": 0.0,
            "close_alignment": 0.0,
        }
    return {
        "n": len(rows),
        "mfe_atr": round(fmean(x.favorable_mfe_atr for x in rows), 4),
        "mae_atr": round(fmean(x.adverse_mae_atr for x in rows), 4),
        "close_return_atr": round(
            fmean(x.signed_close_return_atr for x in rows),
            4,
        ),
        "favorable_dominance": round(
            sum(x.favorable_dominates for x in rows) / len(rows),
            4,
        ),
        "close_alignment": round(
            sum(x.close_aligned for x in rows) / len(rows),
            4,
        ),
    }


if __name__ == "__main__":
    main()
