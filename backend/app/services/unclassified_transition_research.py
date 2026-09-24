from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    ResearchSplit,
)
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.mt4_specs import list_mt4_symbol_specs
from app.services.opportunity_backtester import _simulate_candidate
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.trading_intelligence import _atr_series, _classify_causal_context

DIRECTIONAL_TRANSITION_PATTERNS = {
    OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM,
    OpportunityCausalPattern.COMPRESSION_BREAKOUT,
    OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
    OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH,
}


def first_directional_transition(
    bars: list[MarketBar],
    atr: list[float],
    birth_index: int,
    *,
    episode_side: Side,
    max_wait_bars: int = 3,
) -> tuple[int, OpportunityCausalContext] | None:
    if max_wait_bars <= 0:
        raise ValueError("max_wait_bars must be positive")

    stop = min(len(bars), birth_index + max_wait_bars + 1)
    for index in range(birth_index + 1, stop):
        context = _classify_causal_context(
            bars=bars,
            atr=atr,
            index=index,
            episode_side=episode_side,
        )
        if (
            context.pattern in DIRECTIONAL_TRANSITION_PATTERNS
            and context.side is not None
        ):
            return index, context
    return None


def summarize_waiting_rows(rows: list[dict]) -> dict[str, float | int]:
    transitions = [row for row in rows if row.get("transition_pattern") is not None]
    executed = [row for row in transitions if row.get("result_r") is not None]
    result_values = [float(row["result_r"]) for row in executed]
    gross_profit = sum(value for value in result_values if value > 0)
    gross_loss = -sum(value for value in result_values if value < 0)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in result_values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return {
        "episodes": len(rows),
        "transitions": len(transitions),
        "transition_coverage": (
            len(transitions) / len(rows) if rows else 0.0
        ),
        "alignment_rate": (
            sum(bool(row["aligned"]) for row in transitions) / len(transitions)
            if transitions
            else 0.0
        ),
        "average_wait_bars": (
            fmean(float(row["bars_waited"]) for row in transitions)
            if transitions
            else 0.0
        ),
        "average_move_consumed_atr": (
            fmean(float(row["move_consumed_atr"]) for row in transitions)
            if transitions
            else 0.0
        ),
        "executed": len(executed),
        "expectancy_r": fmean(result_values) if result_values else 0.0,
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0
            else (99.0 if gross_profit > 0 else 0.0)
        ),
        "win_rate": (
            sum(value > 0 for value in result_values) / len(result_values)
            if result_values
            else 0.0
        ),
        "total_r": sum(result_values),
        "max_drawdown_r": max_drawdown,
    }


def analyze_unclassified_transition_waiting(
    files_dir: Path,
    execution_model_path: Path,
    macro_events_path: Path,
    symbols: tuple[str, ...],
    *,
    train_end: datetime,
    validation_end: datetime,
    capital_eur: float,
    move_threshold_atr: float = 1.5,
    market_horizon_bars: int = 12,
    max_wait_bars: int = 3,
    stop_atr_multiple: float = 1.5,
    target_r: float = 1.0,
    trade_horizon_bars: int = 12,
) -> dict[str, object]:
    if train_end >= validation_end:
        raise ValueError("train_end must be earlier than validation_end")
    if capital_eur <= 0:
        raise ValueError("capital_eur must be positive")
    if move_threshold_atr <= 0:
        raise ValueError("move_threshold_atr must be positive")
    if market_horizon_bars <= 0:
        raise ValueError("market_horizon_bars must be positive")
    if max_wait_bars <= 0:
        raise ValueError("max_wait_bars must be positive")
    if stop_atr_multiple <= 0:
        raise ValueError("stop_atr_multiple must be positive")
    if target_r <= 0:
        raise ValueError("target_r must be positive")
    if trade_horizon_bars <= 0:
        raise ValueError("trade_horizon_bars must be positive")

    specs = list_mt4_symbol_specs(files_dir)
    execution_model = load_research_execution_model(execution_model_path)
    macro_events = load_macro_events(macro_events_path)
    split = ResearchSplit(
        train_end=train_end,
        validation_end=validation_end,
    )

    assets: list[dict[str, object]] = []
    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        spec = specs.get(symbol)
        if spec is None:
            continue
        spec = apply_research_execution_model(spec, execution_model)
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
        rows = _asset_waiting_rows(
            bars=bars,
            atr=atr,
            config=config,
            macro_events=macro_events,
            move_threshold_atr=move_threshold_atr,
            market_horizon_bars=market_horizon_bars,
            max_wait_bars=max_wait_bars,
            stop_atr_multiple=stop_atr_multiple,
            target_r=target_r,
            trade_horizon_bars=trade_horizon_bars,
        )
        by_pattern: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            pattern = row.get("transition_pattern")
            if pattern is not None:
                by_pattern[str(pattern)].append(row)

        assets.append(
            {
                "symbol": symbol,
                "all": summarize_waiting_rows(rows),
                "train": summarize_waiting_rows(
                    [row for row in rows if row["birth_at"] < train_end]
                ),
                "validation": summarize_waiting_rows(
                    [
                        row
                        for row in rows
                        if train_end <= row["birth_at"] < validation_end
                    ]
                ),
                "holdout": summarize_waiting_rows(
                    [row for row in rows if row["birth_at"] >= validation_end]
                ),
                "by_transition_pattern": {
                    pattern: summarize_waiting_rows(pattern_rows)
                    for pattern, pattern_rows in sorted(by_pattern.items())
                },
            }
        )

    return {
        "reference_capital_eur": capital_eur,
        "move_threshold_atr": move_threshold_atr,
        "market_horizon_bars": market_horizon_bars,
        "max_wait_bars": max_wait_bars,
        "stop_atr_multiple": stop_atr_multiple,
        "target_r": target_r,
        "trade_horizon_bars": trade_horizon_bars,
        "assets": assets,
    }


def _asset_waiting_rows(
    *,
    bars: list[MarketBar],
    atr: list[float],
    config: OpportunityBacktestConfig,
    macro_events: list,
    move_threshold_atr: float,
    market_horizon_bars: int,
    max_wait_bars: int,
    stop_atr_multiple: float,
    target_r: float,
    trade_horizon_bars: int,
) -> list[dict]:
    if len(bars) < 24 + market_horizon_bars + max_wait_bars + 2:
        return []

    rows: list[dict] = []
    index = 24
    last_index = len(bars) - max(
        market_horizon_bars,
        max_wait_bars + trade_horizon_bars + 1,
    ) - 1
    while index <= last_index:
        bar = bars[index]
        current_atr = atr[index]
        if current_atr <= 0:
            index += 1
            continue

        future = bars[index + 1 : index + 1 + market_horizon_bars]
        up_move = max(item.high for item in future) - bar.close
        down_move = bar.close - min(item.low for item in future)
        up_atr = max(0.0, up_move / current_atr)
        down_atr = max(0.0, down_move / current_atr)
        move_atr = max(up_atr, down_atr)
        if move_atr < move_threshold_atr:
            index += 1
            continue

        episode_side = Side.BUY if up_atr >= down_atr else Side.SELL
        birth_context = _classify_causal_context(
            bars=bars,
            atr=atr,
            index=index,
            episode_side=episode_side,
        )
        birth_at = bar.timestamp + timedelta(minutes=5)
        if birth_context.pattern != OpportunityCausalPattern.UNCLASSIFIED:
            index += market_horizon_bars
            continue

        transition = first_directional_transition(
            bars,
            atr,
            index,
            episode_side=episode_side,
            max_wait_bars=max_wait_bars,
        )
        row: dict[str, object] = {
            "birth_at": birth_at,
            "episode_side": episode_side.value,
            "move_atr": move_atr,
            "transition_pattern": None,
            "transition_side": None,
            "aligned": False,
            "bars_waited": 0,
            "move_consumed_atr": 0.0,
            "result_r": None,
            "rejection_reason": None,
        }
        if transition is None:
            rows.append(row)
            index += market_horizon_bars
            continue

        transition_index, context = transition
        entry_index = transition_index + 1
        if entry_index >= len(bars):
            rows.append(row)
            index += market_horizon_bars
            continue

        entry = bars[entry_index].open
        stop_distance = stop_atr_multiple * atr[transition_index]
        stop = (
            entry - stop_distance
            if context.side == Side.BUY
            else entry + stop_distance
        )
        move_consumed = (
            entry - bar.close
            if episode_side == Side.BUY
            else bar.close - entry
        ) / current_atr

        row.update(
            {
                "transition_pattern": context.pattern.value,
                "transition_side": context.side.value if context.side else None,
                "aligned": context.side == episode_side,
                "bars_waited": transition_index - index,
                "move_consumed_atr": move_consumed,
            }
        )
        if stop <= 0:
            row["rejection_reason"] = "invalid stop"
            rows.append(row)
            index += market_horizon_bars
            continue

        candidate = OpportunityCandidate(
            symbol=bar.symbol,
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=context.side,
            signal_at=bars[transition_index].timestamp + timedelta(minutes=5),
            entry_at=bars[entry_index].timestamp,
            signal_index=transition_index,
            entry_index=entry_index,
            structural_stop=stop,
            target_r=target_r,
            max_holding_bars=trade_horizon_bars,
            reason=(
                "first directional transition after unclassified opportunity birth"
            ),
        )
        if active_macro_blackouts(macro_events, candidate.entry_at):
            row["rejection_reason"] = "macro blackout"
            rows.append(row)
            index += market_horizon_bars
            continue

        outcome, _, rejection = _simulate_candidate(
            bars,
            candidate,
            config,
        )
        row["rejection_reason"] = rejection
        if outcome is not None:
            row["result_r"] = outcome.result_r
        rows.append(row)
        index += market_horizon_bars

    return rows
