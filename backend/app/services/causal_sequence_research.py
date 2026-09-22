from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from app.domain.causal_sequence_research import (
    AssetCausalSequenceResearch,
    CausalSequenceHistoricalSummary,
    CausalSequenceResearchReport,
    CausalSequenceSplitSummary,
    PredictiveLiftConsistency,
)
from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.causal_economic_matrix import _directional_consistency
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.trading_intelligence import _atr_series, _classify_causal_context

DEFAULT_SEQUENCE_LENGTH = 3
DEFAULT_MOVE_THRESHOLD_ATR = 1.5
DEFAULT_HORIZON_BARS = 12


def build_causal_sequence_research_report(
    files_dir: Path,
    symbols: tuple[str, ...],
    *,
    generated_at: datetime,
    train_end: datetime,
    validation_end: datetime,
    sequence_length: int = DEFAULT_SEQUENCE_LENGTH,
    move_threshold_atr: float = DEFAULT_MOVE_THRESHOLD_ATR,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
) -> CausalSequenceResearchReport:
    if train_end >= validation_end:
        raise ValueError("train_end must be earlier than validation_end")
    if sequence_length < 2 or sequence_length > 6:
        raise ValueError("sequence_length must be between 2 and 6")
    if move_threshold_atr <= 0:
        raise ValueError("move_threshold_atr must be positive")
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be positive")

    assets = [
        _analyze_asset_sequences(
            files_dir,
            symbol,
            train_end=train_end,
            validation_end=validation_end,
            sequence_length=sequence_length,
            move_threshold_atr=move_threshold_atr,
            horizon_bars=horizon_bars,
        )
        for symbol in symbols
    ]
    return CausalSequenceResearchReport(
        generated_at=generated_at,
        train_end=train_end,
        validation_end=validation_end,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
        sequence_length=sequence_length,
        assets=assets,
    )


def _analyze_asset_sequences(
    files_dir: Path,
    symbol: str,
    *,
    train_end: datetime,
    validation_end: datetime,
    sequence_length: int,
    move_threshold_atr: float,
    horizon_bars: int,
) -> AssetCausalSequenceResearch:
    bars = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    atr = _atr_series(bars)
    rows = _historical_sequence_episodes(
        bars=bars,
        atr=atr,
        sequence_length=sequence_length,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
    )
    occurrences = _historical_sequence_occurrences(
        bars=bars,
        atr=atr,
        sequence_length=sequence_length,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
    )

    grouped: dict[tuple[OpportunityCausalPattern, ...], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row["sequence"])].append(row)

    occurrence_grouped: dict[
        tuple[OpportunityCausalPattern, ...],
        list[dict],
    ] = defaultdict(list)
    for row in occurrences:
        occurrence_grouped[tuple(row["sequence"])].append(row)

    baseline_train = _baseline_success_rate(
        [row for row in occurrences if row["birth_at"] < train_end]
    )
    baseline_validation = _baseline_success_rate(
        [
            row
            for row in occurrences
            if train_end <= row["birth_at"] < validation_end
        ]
    )
    baseline_holdout = _baseline_success_rate(
        [row for row in occurrences if row["birth_at"] >= validation_end]
    )
    baseline_first_touch_train = _baseline_first_touch_success_rate(
        [row for row in occurrences if row["birth_at"] < train_end]
    )
    baseline_first_touch_validation = _baseline_first_touch_success_rate(
        [
            row
            for row in occurrences
            if train_end <= row["birth_at"] < validation_end
        ]
    )
    baseline_first_touch_holdout = _baseline_first_touch_success_rate(
        [row for row in occurrences if row["birth_at"] >= validation_end]
    )

    sequences: list[CausalSequenceHistoricalSummary] = []
    for sequence, sequence_rows in grouped.items():
        sequence_occurrences = occurrence_grouped.get(sequence, [])
        train = _split_summary(
            [row for row in sequence_rows if row["birth_at"] < train_end],
            [row for row in sequence_occurrences if row["birth_at"] < train_end],
            baseline_train,
            baseline_first_touch_train,
        )
        validation = _split_summary(
            [
                row
                for row in sequence_rows
                if train_end <= row["birth_at"] < validation_end
            ],
            [
                row
                for row in sequence_occurrences
                if train_end <= row["birth_at"] < validation_end
            ],
            baseline_validation,
            baseline_first_touch_validation,
        )
        holdout = _split_summary(
            [row for row in sequence_rows if row["birth_at"] >= validation_end],
            [row for row in sequence_occurrences if row["birth_at"] >= validation_end],
            baseline_holdout,
            baseline_first_touch_holdout,
        )
        sequences.append(
            CausalSequenceHistoricalSummary(
                sequence=list(sequence),
                directional_consistency=_directional_consistency(
                    train.alignment_rate,
                    validation.alignment_rate,
                    holdout.alignment_rate,
                ),
                predictive_lift_consistency=_predictive_lift_consistency(
                    train.lift_vs_baseline,
                    validation.lift_vs_baseline,
                    holdout.lift_vs_baseline,
                ),
                first_touch_lift_consistency=_predictive_lift_consistency(
                    train.first_touch_lift_vs_baseline,
                    validation.first_touch_lift_vs_baseline,
                    holdout.first_touch_lift_vs_baseline,
                ),
                train=train,
                validation=validation,
                holdout=holdout,
            )
        )

    return AssetCausalSequenceResearch(
        symbol=symbol,
        total_episodes=len(rows),
        sequences=sorted(
            sequences,
            key=lambda row: (
                -(
                    row.train.episodes
                    + row.validation.episodes
                    + row.holdout.episodes
                ),
                tuple(item.value for item in row.sequence),
            ),
        ),
    )


def _historical_sequence_occurrences(
    *,
    bars: list[MarketBar],
    atr: list[float],
    sequence_length: int,
    move_threshold_atr: float,
    horizon_bars: int,
) -> list[dict]:
    minimum_index = max(24, sequence_length - 1)
    if len(bars) < minimum_index + horizon_bars + 1:
        return []

    rows: list[dict] = []
    last_index = len(bars) - horizon_bars - 1
    for index in range(minimum_index, last_index + 1):
        bar = bars[index]
        current_atr = atr[index]
        if current_atr <= 0:
            continue

        contexts = [
            _classify_causal_context(
                bars=bars,
                atr=atr,
                index=context_index,
                episode_side=Side.BUY,
            )
            for context_index in range(index - sequence_length + 1, index + 1)
        ]
        sequence_side = _sequence_direction(contexts)
        future = bars[index + 1 : index + 1 + horizon_bars]

        directional_success: bool | None = None
        if sequence_side == Side.BUY:
            favorable_atr = (
                max(item.high for item in future) - bar.close
            ) / current_atr
            directional_success = favorable_atr >= move_threshold_atr
        elif sequence_side == Side.SELL:
            favorable_atr = (
                bar.close - min(item.low for item in future)
            ) / current_atr
            directional_success = favorable_atr >= move_threshold_atr

        first_touch_success = _first_touch_directional_success(
            bars=bars,
            index=index,
            atr_value=current_atr,
            side=sequence_side,
            threshold_atr=move_threshold_atr,
            horizon_bars=horizon_bars,
        )

        rows.append(
            {
                "birth_at": bar.timestamp + timedelta(minutes=5),
                "sequence": [context.pattern for context in contexts],
                "sequence_side": sequence_side,
                "directional_success": directional_success,
                "first_touch_success": first_touch_success,
            }
        )
    return rows


def _baseline_success_rate(rows: list[dict]) -> float | None:
    directional = [
        row for row in rows if row["directional_success"] is not None
    ]
    if not directional:
        return None
    return sum(
        row["directional_success"] is True for row in directional
    ) / len(directional)


def _baseline_first_touch_success_rate(rows: list[dict]) -> float | None:
    directional = [
        row for row in rows if row["first_touch_success"] is not None
    ]
    if not directional:
        return None
    return sum(
        row["first_touch_success"] is True for row in directional
    ) / len(directional)


def _first_touch_directional_success(
    *,
    bars: list[MarketBar],
    index: int,
    atr_value: float,
    side: Side | None,
    threshold_atr: float,
    horizon_bars: int,
) -> bool | None:
    if side is None or atr_value <= 0:
        return None

    entry = bars[index].close
    distance = threshold_atr * atr_value
    target = entry + distance if side == Side.BUY else entry - distance
    stop = entry - distance if side == Side.BUY else entry + distance

    for bar in bars[index + 1 : index + 1 + horizon_bars]:
        target_hit = bar.high >= target if side == Side.BUY else bar.low <= target
        stop_hit = bar.low <= stop if side == Side.BUY else bar.high >= stop
        if target_hit and stop_hit:
            return None
        if target_hit:
            return True
        if stop_hit:
            return False
    return False


def _predictive_lift_consistency(
    train_lift: float | None,
    validation_lift: float | None,
    holdout_lift: float | None,
) -> PredictiveLiftConsistency:
    lifts = (train_lift, validation_lift, holdout_lift)
    if any(lift is None for lift in lifts):
        return PredictiveLiftConsistency.INSUFFICIENT

    concrete = tuple(float(lift) for lift in lifts if lift is not None)
    if all(lift > 1.0 for lift in concrete):
        return PredictiveLiftConsistency.ABOVE_BASELINE_STABLE
    if all(lift < 1.0 for lift in concrete):
        return PredictiveLiftConsistency.BELOW_BASELINE_STABLE
    return PredictiveLiftConsistency.MIXED


def _historical_sequence_episodes(
    *,
    bars: list[MarketBar],
    atr: list[float],
    sequence_length: int,
    move_threshold_atr: float,
    horizon_bars: int,
) -> list[dict]:
    minimum_index = max(24, sequence_length - 1)
    if len(bars) < minimum_index + horizon_bars + 1:
        return []

    rows: list[dict] = []
    index = minimum_index
    last_index = len(bars) - horizon_bars - 1

    while index <= last_index:
        bar = bars[index]
        current_atr = atr[index]
        if current_atr <= 0:
            index += 1
            continue

        future = bars[index + 1 : index + 1 + horizon_bars]
        up_move = max(item.high for item in future) - bar.close
        down_move = bar.close - min(item.low for item in future)
        up_atr = max(0.0, up_move / current_atr)
        down_atr = max(0.0, down_move / current_atr)
        move_atr = max(up_atr, down_atr)
        if move_atr < move_threshold_atr:
            index += 1
            continue

        episode_side = Side.BUY if up_atr >= down_atr else Side.SELL
        contexts = [
            _classify_causal_context(
                bars=bars,
                atr=atr,
                index=context_index,
                episode_side=episode_side,
            )
            for context_index in range(index - sequence_length + 1, index + 1)
        ]
        sequence_side = _sequence_direction(contexts)
        aligned = (
            sequence_side == episode_side
            if sequence_side is not None
            else None
        )
        rows.append(
            {
                "birth_at": bar.timestamp + timedelta(minutes=5),
                "move_atr": move_atr,
                "sequence": [context.pattern for context in contexts],
                "sequence_side": sequence_side,
                "aligned": aligned,
            }
        )
        index += horizon_bars

    return rows


def _sequence_direction(
    contexts: list[OpportunityCausalContext],
) -> Side | None:
    for context in reversed(contexts):
        if context.side is not None:
            return context.side
    return None


def _split_summary(
    rows: list[dict],
    occurrence_rows: list[dict],
    asset_baseline_success_rate: float | None,
    asset_baseline_first_touch_success_rate: float | None,
) -> CausalSequenceSplitSummary:
    aligned = sum(row["aligned"] is True for row in rows)
    opposed = sum(row["aligned"] is False for row in rows)
    no_direction = sum(row["aligned"] is None for row in rows)
    directional = aligned + opposed

    directional_occurrences = [
        row
        for row in occurrence_rows
        if row["directional_success"] is not None
    ]
    successes = sum(
        row["directional_success"] is True
        for row in directional_occurrences
    )
    success_rate = (
        successes / len(directional_occurrences)
        if directional_occurrences
        else None
    )
    lift = (
        success_rate / asset_baseline_success_rate
        if success_rate is not None
        and asset_baseline_success_rate is not None
        and asset_baseline_success_rate > 0
        else None
    )

    first_touch_occurrences = [
        row
        for row in occurrence_rows
        if row["first_touch_success"] is not None
    ]
    first_touch_successes = sum(
        row["first_touch_success"] is True
        for row in first_touch_occurrences
    )
    first_touch_success_rate = (
        first_touch_successes / len(first_touch_occurrences)
        if first_touch_occurrences
        else None
    )
    first_touch_lift = (
        first_touch_success_rate / asset_baseline_first_touch_success_rate
        if first_touch_success_rate is not None
        and asset_baseline_first_touch_success_rate is not None
        and asset_baseline_first_touch_success_rate > 0
        else None
    )

    return CausalSequenceSplitSummary(
        episodes=len(rows),
        directional_episodes=directional,
        aligned=aligned,
        opposed=opposed,
        no_direction=no_direction,
        alignment_rate=(aligned / directional) if directional else None,
        average_move_atr=(
            fmean(float(row["move_atr"]) for row in rows)
            if rows
            else 0.0
        ),
        occurrences=len(occurrence_rows),
        directional_occurrences=len(directional_occurrences),
        directional_successes=successes,
        directional_success_rate=success_rate,
        asset_baseline_success_rate=asset_baseline_success_rate,
        lift_vs_baseline=lift,
        first_touch_occurrences=len(first_touch_occurrences),
        first_touch_successes=first_touch_successes,
        first_touch_success_rate=first_touch_success_rate,
        asset_baseline_first_touch_success_rate=(
            asset_baseline_first_touch_success_rate
        ),
        first_touch_lift_vs_baseline=first_touch_lift,
    )
