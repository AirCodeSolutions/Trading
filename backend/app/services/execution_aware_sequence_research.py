from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.domain.execution_aware_sequence_research import (
    AssetExecutionAwareSequenceResearch,
    ExecutionAwareConsistency,
    ExecutionAwareSequenceResearchReport,
    ExecutionAwareSequenceSummary,
    ExecutionAwareSplitSummary,
)
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    ResearchSplit,
)
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.causal_sequence_research import _sequence_direction
from app.services.economic_feasibility import build_economic_feasibility_report
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import _simulate_candidate, _summary
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.trading_intelligence import _atr_series, _classify_causal_context

DEFAULT_SEQUENCE_LENGTH = 3
DEFAULT_TARGET_R = 1.0
DEFAULT_MAX_HOLDING_BARS = 12
MIN_TRAIN_EXECUTED = 30
MIN_VALIDATION_EXECUTED = 10
MIN_HOLDOUT_EXECUTED = 5

_SIZING_REJECTIONS = {
    "spread consumes too much of the stop distance",
    "minimum broker lot exceeds the risk budget",
    "rounded size falls below the broker minimum lot",
    "estimated margin exceeds capital policy",
}


def build_execution_aware_sequence_report(
    files_dir: Path,
    execution_model_path: Path,
    macro_events_path: Path,
    symbols: tuple[str, ...],
    *,
    generated_at: datetime,
    train_end: datetime,
    validation_end: datetime,
    sequence_length: int = DEFAULT_SEQUENCE_LENGTH,
    target_r: float = DEFAULT_TARGET_R,
    max_holding_bars: int = DEFAULT_MAX_HOLDING_BARS,
    capital_eur: float | None = None,
) -> ExecutionAwareSequenceResearchReport:
    if train_end >= validation_end:
        raise ValueError("train_end must be earlier than validation_end")
    if sequence_length < 2 or sequence_length > 6:
        raise ValueError("sequence_length must be between 2 and 6")
    if target_r <= 0:
        raise ValueError("target_r must be positive")
    if max_holding_bars <= 0:
        raise ValueError("max_holding_bars must be positive")

    selected_capital = capital_eur or settings.reference_capital_eur
    if selected_capital <= 0:
        raise ValueError("capital_eur must be positive")

    economic = build_economic_feasibility_report(
        files_dir,
        execution_model_path,
        symbols,
        generated_at=generated_at,
        capital_eur=selected_capital,
    )
    economic_by_symbol = {asset.symbol: asset for asset in economic.assets}
    execution_model = load_research_execution_model(execution_model_path)
    live_specs = list_mt4_symbol_specs(files_dir)
    macro_events = load_macro_events(macro_events_path)
    split = ResearchSplit(
        train_end=train_end,
        validation_end=validation_end,
    )

    assets: list[AssetExecutionAwareSequenceResearch] = []
    for symbol in symbols:
        normalized = symbol.upper()
        economic_asset = economic_by_symbol[normalized]
        raw_spec = live_specs.get(normalized)
        if raw_spec is None:
            raise ValueError(f"broker symbol spec missing for {normalized}")
        spec = apply_research_execution_model(raw_spec, execution_model)

        if not economic_asset.feasible_stop_interval:
            assets.append(
                AssetExecutionAwareSequenceResearch(
                    symbol=normalized,
                    feasible_stop_interval=False,
                    stop_atr_multiple=None,
                    baseline_train_expectancy_r=0.0,
                    baseline_validation_expectancy_r=0.0,
                    baseline_holdout_expectancy_r=0.0,
                    sequences=[],
                )
            )
            continue

        best_profile = max(
            economic_asset.stop_profiles,
            key=lambda row: (
                row.approval_rate,
                -row.stop_atr_multiple,
            ),
        )
        assets.append(
            _analyze_asset(
                files_dir,
                normalized,
                spec=spec,
                macro_events=macro_events,
                split=split,
                sequence_length=sequence_length,
                stop_atr_multiple=best_profile.stop_atr_multiple,
                target_r=target_r,
                max_holding_bars=max_holding_bars,
                capital_eur=selected_capital,
            )
        )

    return ExecutionAwareSequenceResearchReport(
        generated_at=generated_at,
        train_end=train_end,
        validation_end=validation_end,
        sequence_length=sequence_length,
        target_r=target_r,
        max_holding_bars=max_holding_bars,
        reference_capital_eur=selected_capital,
        assets=assets,
    )


def _analyze_asset(
    files_dir: Path,
    symbol: str,
    *,
    spec,
    macro_events,
    split: ResearchSplit,
    sequence_length: int,
    stop_atr_multiple: float,
    target_r: float,
    max_holding_bars: int,
    capital_eur: float,
) -> AssetExecutionAwareSequenceResearch:
    bars = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    atr = _atr_series(bars)
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        split=split,
        capital_eur=capital_eur,
        macro_events=macro_events,
    )

    records = _execution_aware_occurrences(
        bars=bars,
        atr=atr,
        config=config,
        sequence_length=sequence_length,
        stop_atr_multiple=stop_atr_multiple,
        target_r=target_r,
        max_holding_bars=max_holding_bars,
    )

    train_records = [row for row in records if row["signal_at"] < split.train_end]
    validation_records = [
        row
        for row in records
        if split.train_end <= row["signal_at"] < split.validation_end
    ]
    holdout_records = [
        row for row in records if row["signal_at"] >= split.validation_end
    ]

    baseline_train = _records_performance(train_records)
    baseline_validation = _records_performance(validation_records)
    baseline_holdout = _records_performance(holdout_records)

    grouped: dict[tuple[OpportunityCausalPattern, ...], list[dict]] = defaultdict(list)
    for row in records:
        grouped[tuple(row["sequence"])].append(row)

    sequences: list[ExecutionAwareSequenceSummary] = []
    for sequence, sequence_records in grouped.items():
        train = _summarize_split(
            [row for row in sequence_records if row["signal_at"] < split.train_end],
            baseline_train.expectancy_r,
        )
        validation = _summarize_split(
            [
                row
                for row in sequence_records
                if split.train_end <= row["signal_at"] < split.validation_end
            ],
            baseline_validation.expectancy_r,
        )
        holdout = _summarize_split(
            [
                row
                for row in sequence_records
                if row["signal_at"] >= split.validation_end
            ],
            baseline_holdout.expectancy_r,
        )
        sequences.append(
            ExecutionAwareSequenceSummary(
                sequence=list(sequence),
                consistency=_execution_consistency(train, validation, holdout),
                stop_atr_multiple=stop_atr_multiple,
                target_r=target_r,
                train=train,
                validation=validation,
                holdout=holdout,
            )
        )

    return AssetExecutionAwareSequenceResearch(
        symbol=symbol,
        feasible_stop_interval=True,
        stop_atr_multiple=stop_atr_multiple,
        baseline_train_expectancy_r=baseline_train.expectancy_r,
        baseline_validation_expectancy_r=baseline_validation.expectancy_r,
        baseline_holdout_expectancy_r=baseline_holdout.expectancy_r,
        sequences=sorted(
            sequences,
            key=lambda row: (
                row.consistency != ExecutionAwareConsistency.POSITIVE_STABLE,
                -(
                    row.train.executed
                    + row.validation.executed
                    + row.holdout.executed
                ),
                tuple(item.value for item in row.sequence),
            ),
        ),
    )


def _execution_aware_occurrences(
    *,
    bars,
    atr: list[float],
    config: OpportunityBacktestConfig,
    sequence_length: int,
    stop_atr_multiple: float,
    target_r: float,
    max_holding_bars: int,
) -> list[dict]:
    minimum_index = max(24, sequence_length - 1)
    last_index = len(bars) - max_holding_bars - 1
    if last_index < minimum_index:
        return []

    records: list[dict] = []
    for index in range(minimum_index, last_index + 1):
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
        side = _sequence_direction(contexts)
        if side is None:
            continue

        entry_index = index + 1
        entry_reference = bars[entry_index].open
        stop_distance = stop_atr_multiple * current_atr
        structural_stop = (
            entry_reference - stop_distance
            if side == Side.BUY
            else entry_reference + stop_distance
        )
        if structural_stop <= 0:
            continue

        candidate = OpportunityCandidate(
            symbol=config.spec.symbol,
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=side,
            signal_at=bars[index].timestamp + timedelta(minutes=5),
            entry_at=bars[entry_index].timestamp,
            signal_index=index,
            entry_index=entry_index,
            structural_stop=structural_stop,
            target_r=target_r,
            max_holding_bars=max_holding_bars,
            reason="execution-aware causal sequence screening",
        )

        rejection: str | None = None
        outcome = None
        if active_macro_blackouts(config.macro_events, candidate.entry_at):
            rejection = "macro"
        else:
            outcome, _, rejection = _simulate_candidate(bars, candidate, config)

        records.append(
            {
                "sequence": [context.pattern for context in contexts],
                "signal_at": candidate.signal_at,
                "outcome": outcome,
                "rejection": rejection,
            }
        )
    return records


def _records_performance(records: list[dict]):
    return _summary(
        [row["outcome"] for row in records if row["outcome"] is not None]
    )


def _summarize_split(
    records: list[dict],
    baseline_expectancy_r: float,
) -> ExecutionAwareSplitSummary:
    outcomes = [row["outcome"] for row in records if row["outcome"] is not None]
    performance = _summary(outcomes)

    rejected_macro = sum(row["rejection"] == "macro" for row in records)
    rejected_sizing = sum(
        row["rejection"] in _SIZING_REJECTIONS for row in records
    )
    rejected_other = len(records) - len(outcomes) - rejected_macro - rejected_sizing

    return ExecutionAwareSplitSummary(
        occurrences=len(records),
        executed=performance.trades,
        rejected_macro=rejected_macro,
        rejected_sizing=rejected_sizing,
        rejected_other=max(0, rejected_other),
        total_r=performance.total_r,
        expectancy_r=performance.expectancy_r,
        profit_factor=performance.profit_factor,
        win_rate=performance.win_rate,
        max_drawdown_r=performance.max_drawdown_r,
        average_execution_cost_r=performance.average_execution_cost_r,
        asset_baseline_expectancy_r=baseline_expectancy_r,
        expectancy_delta_vs_baseline_r=(
            performance.expectancy_r - baseline_expectancy_r
        ),
    )


def _execution_consistency(
    train: ExecutionAwareSplitSummary,
    validation: ExecutionAwareSplitSummary,
    holdout: ExecutionAwareSplitSummary,
) -> ExecutionAwareConsistency:
    if (
        train.executed < MIN_TRAIN_EXECUTED
        or validation.executed < MIN_VALIDATION_EXECUTED
        or holdout.executed < MIN_HOLDOUT_EXECUTED
    ):
        return ExecutionAwareConsistency.INSUFFICIENT

    values = (
        train.expectancy_r,
        validation.expectancy_r,
        holdout.expectancy_r,
    )
    if all(value > 0 for value in values):
        return ExecutionAwareConsistency.POSITIVE_STABLE
    if all(value < 0 for value in values):
        return ExecutionAwareConsistency.NEGATIVE_STABLE
    return ExecutionAwareConsistency.MIXED
