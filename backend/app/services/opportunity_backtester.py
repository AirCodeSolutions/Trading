from collections.abc import Sequence
from itertools import pairwise

from app.domain.admission import EvidenceWindow, StrategyEvidence
from app.domain.broker import PositionSizeRequest
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityBacktestResult,
    OpportunityCandidate,
    PerformanceSummary,
    TradeOutcome,
    rejection_counter,
)
from app.domain.trading import Side
from app.services.admission import assess_strategy
from app.services.capital_risk import size_position
from app.services.opportunity_strategies import generate_candidates


def run_opportunity_backtest(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    config: OpportunityBacktestConfig,
) -> OpportunityBacktestResult:
    _validate_inputs(bars_m5, bars_m15, config)
    candidates = generate_candidates(bars_m5, bars_m15, config.mechanism)
    outcomes: list[TradeOutcome] = []
    rejections: list[str] = []
    busy_until = -1

    for candidate in candidates:
        if candidate.entry_index <= busy_until:
            rejections.append("overlapping_position")
            continue

        outcome, exit_index, rejection = _simulate_candidate(
            bars_m5,
            candidate,
            config,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        if outcome is None or exit_index is None:
            rejections.append("simulation_failed")
            continue

        outcomes.append(outcome)
        busy_until = exit_index

    train = _summary(
        [item for item in outcomes if item.signal_at < config.split.train_end]
    )
    validation = _summary(
        [
            item
            for item in outcomes
            if config.split.train_end <= item.signal_at < config.split.validation_end
        ]
    )
    holdout = _summary(
        [item for item in outcomes if item.signal_at >= config.split.validation_end]
    )

    evidence = StrategyEvidence(
        strategy_id=f"{config.spec.symbol}:{config.mechanism}",
        train=_evidence_window(train),
        validation=_evidence_window(validation),
        holdout=_evidence_window(holdout),
    )

    return OpportunityBacktestResult(
        symbol=config.spec.symbol.upper(),
        mechanism=config.mechanism,
        candidates=len(candidates),
        executed=len(outcomes),
        rejected=len(rejections),
        rejection_reasons=rejection_counter(rejections),
        train=train,
        validation=validation,
        holdout=holdout,
        admission=assess_strategy(evidence),
    )


def _validate_inputs(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    config: OpportunityBacktestConfig,
) -> None:
    if not bars_m5 or not bars_m15:
        raise ValueError("M5 and M15 bars are required")
    if any(bar.timeframe != Timeframe.M5 for bar in bars_m5):
        raise ValueError("bars_m5 must contain M5 bars only")
    if any(bar.timeframe != Timeframe.M15 for bar in bars_m15):
        raise ValueError("bars_m15 must contain M15 bars only")

    expected_symbol = config.spec.symbol.upper()
    symbols = {
        *(bar.symbol.upper() for bar in bars_m5),
        *(bar.symbol.upper() for bar in bars_m15),
    }
    if symbols != {expected_symbol}:
        raise ValueError("bar symbols must match the broker symbol spec")

    if any(current.timestamp <= previous.timestamp for previous, current in pairwise(bars_m5)):
        raise ValueError("M5 bars must be strictly chronological")
    if any(current.timestamp <= previous.timestamp for previous, current in pairwise(bars_m15)):
        raise ValueError("M15 bars must be strictly chronological")


def _simulate_candidate(
    bars: Sequence[MarketBar],
    candidate: OpportunityCandidate,
    config: OpportunityBacktestConfig,
) -> tuple[TradeOutcome | None, int | None, str | None]:
    if candidate.entry_index >= len(bars):
        return None, None, "missing_entry_bar"

    spec = config.spec
    entry_bar = bars[candidate.entry_index]
    spread = spec.spread
    slippage = spread * config.slippage_spread_fraction

    if candidate.side == Side.BUY:
        entry = entry_bar.open + spread + slippage
        stop = candidate.structural_stop
        risk_distance = entry - stop
    else:
        entry = entry_bar.open - slippage
        stop = candidate.structural_stop + spread
        risk_distance = stop - entry

    if risk_distance <= 0:
        return None, None, "invalid_stop_geometry"

    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=entry,
            stop=stop,
            requested_risk_fraction=config.requested_risk_fraction,
        )
    )
    if not sizing.approved:
        return None, None, sizing.reason

    execution_cost_r = (spread + slippage) / risk_distance
    last_index = min(
        len(bars) - 1,
        candidate.entry_index + candidate.max_holding_bars - 1,
    )
    result_r: float | None = None
    exit_reason = "timeout"
    exit_index = last_index

    if candidate.side == Side.BUY:
        target_bid = entry + candidate.target_r * risk_distance
        for index in range(candidate.entry_index, last_index + 1):
            bar = bars[index]
            stop_hit = bar.low <= stop
            target_hit = bar.high >= target_bid
            if stop_hit:
                result_r = -1.0
                exit_reason = "stop"
                exit_index = index
                break
            if target_hit:
                result_r = candidate.target_r
                exit_reason = "target"
                exit_index = index
                break
        if result_r is None:
            result_r = (bars[last_index].close - entry) / risk_distance
    else:
        target_ask = entry - candidate.target_r * risk_distance
        for index in range(candidate.entry_index, last_index + 1):
            bar = bars[index]
            ask_high = bar.high + spread
            ask_low = bar.low + spread
            stop_hit = ask_high >= stop
            target_hit = ask_low <= target_ask
            if stop_hit:
                result_r = -1.0
                exit_reason = "stop"
                exit_index = index
                break
            if target_hit:
                result_r = candidate.target_r
                exit_reason = "target"
                exit_index = index
                break
        if result_r is None:
            exit_ask = bars[last_index].close + spread
            result_r = (entry - exit_ask) / risk_distance

    pnl_eur = result_r * sizing.expected_loss_eur
    return (
        TradeOutcome(
            symbol=candidate.symbol,
            mechanism=candidate.mechanism,
            side=candidate.side,
            signal_at=candidate.signal_at,
            entry_at=candidate.entry_at,
            exit_at=bars[exit_index].timestamp,
            lots=sizing.lots,
            risk_eur=sizing.expected_loss_eur,
            result_r=result_r,
            pnl_eur=pnl_eur,
            execution_cost_r=execution_cost_r,
            exit_reason=exit_reason,
        ),
        exit_index,
        None,
    )


def _summary(outcomes: Sequence[TradeOutcome]) -> PerformanceSummary:
    if not outcomes:
        return PerformanceSummary(
            trades=0,
            total_r=0,
            expectancy_r=0,
            profit_factor=0,
            win_rate=0,
            max_drawdown_r=0,
            total_pnl_eur=0,
            average_execution_cost_r=0,
        )

    results = [item.result_r for item in outcomes]
    gains = sum(value for value in results if value > 0)
    losses = -sum(value for value in results if value < 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in results:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    profit_factor = gains / losses if losses > 0 else 99.0
    return PerformanceSummary(
        trades=len(outcomes),
        total_r=sum(results),
        expectancy_r=sum(results) / len(results),
        profit_factor=profit_factor,
        win_rate=sum(value > 0 for value in results) / len(results),
        max_drawdown_r=max_drawdown,
        total_pnl_eur=sum(item.pnl_eur for item in outcomes),
        average_execution_cost_r=(
            sum(item.execution_cost_r for item in outcomes) / len(outcomes)
        ),
    )


def _evidence_window(summary: PerformanceSummary) -> EvidenceWindow:
    return EvidenceWindow(
        trades=summary.trades,
        expectancy_r=summary.expectancy_r,
        profit_factor=summary.profit_factor,
        max_drawdown_r=summary.max_drawdown_r,
    )
