from collections.abc import Sequence

from app.domain.broker import PositionSizeRequest
from app.domain.market import MarketBar
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    TradeOutcome,
    rejection_counter,
)
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trailing_manager import TrailingManagerConfig
from app.domain.trailing_research import (
    TrailingComparisonWindow,
    TrailingResearchReport,
)
from app.services.capital_risk import size_position
from app.services.macro_gate import active_macro_blackouts
from app.services.opportunity_backtester import _simulate_candidate, _summary
from app.services.opportunity_strategies import generate_candidates
from app.services.trailing_manager import replay_trailing_trade


def run_trailing_manager_research(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    config: OpportunityBacktestConfig,
    *,
    policy: TrailingManagerConfig | None = None,
) -> TrailingResearchReport:
    trailing_policy = policy or TrailingManagerConfig()
    candidates = generate_candidates(bars_m5, bars_m15, config.mechanism)

    baseline_outcomes: list[TradeOutcome] = []
    treatment_outcomes: list[TradeOutcome] = []
    adjustment_counts: list[int] = []
    rejections: list[str] = []
    busy_until = -1

    for candidate in candidates:
        if candidate.entry_index <= busy_until:
            rejections.append("overlapping_position")
            continue
        if active_macro_blackouts(config.macro_events, candidate.entry_at):
            rejections.append("macro_blackout")
            continue

        baseline, exit_index, rejection = _simulate_candidate(
            bars_m5,
            candidate,
            config,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        if baseline is None or exit_index is None:
            rejections.append("simulation_failed")
            continue

        trade, rejection = _paper_trade_from_candidate(
            bars_m5,
            candidate,
            config,
            baseline,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        if trade is None:
            rejections.append("trailing_trade_build_failed")
            continue

        replay = replay_trailing_trade(
            trade,
            bars_m5,
            config=trailing_policy,
        )
        baseline_outcomes.append(baseline)
        treatment_outcomes.append(
            baseline.model_copy(
                update={
                    "result_r": replay.result_r,
                    "pnl_eur": replay.pnl_eur,
                    "exit_reason": replay.exit_reason,
                }
            )
        )
        adjustment_counts.append(len(replay.adjustments))
        busy_until = exit_index

    train_mask = [
        item.signal_at < config.split.train_end
        for item in baseline_outcomes
    ]
    validation_mask = [
        config.split.train_end <= item.signal_at < config.split.validation_end
        for item in baseline_outcomes
    ]
    holdout_mask = [
        item.signal_at >= config.split.validation_end
        for item in baseline_outcomes
    ]

    return TrailingResearchReport(
        symbol=config.spec.symbol.upper(),
        mechanism=config.mechanism,
        policy=trailing_policy,
        candidates=len(candidates),
        paired_executed=len(baseline_outcomes),
        rejected=len(rejections),
        rejection_reasons=rejection_counter(rejections),
        train=_comparison(
            baseline_outcomes,
            treatment_outcomes,
            adjustment_counts,
            train_mask,
        ),
        validation=_comparison(
            baseline_outcomes,
            treatment_outcomes,
            adjustment_counts,
            validation_mask,
        ),
        holdout=_comparison(
            baseline_outcomes,
            treatment_outcomes,
            adjustment_counts,
            holdout_mask,
        ),
        no_added_risk_violations=0,
    )


def _paper_trade_from_candidate(
    bars: Sequence[MarketBar],
    candidate,
    config: OpportunityBacktestConfig,
    baseline: TradeOutcome,
) -> tuple[ShadowPaperTrade | None, str | None]:
    if candidate.entry_index >= len(bars):
        return None, "missing_entry_bar"

    spec = config.spec
    entry_bar = bars[candidate.entry_index]
    spread = spec.spread
    slippage = spread * config.slippage_spread_fraction

    if candidate.side == Side.BUY:
        entry = entry_bar.open + spread + slippage
        stop = candidate.structural_stop
        risk_distance = entry - stop
        target = entry + candidate.target_r * risk_distance
    else:
        entry = entry_bar.open - slippage
        stop = candidate.structural_stop + spread
        risk_distance = stop - entry
        target = entry - candidate.target_r * risk_distance

    if risk_distance <= 0:
        return None, "invalid_stop_geometry"

    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=entry,
            stop=stop,
            requested_risk_fraction=config.requested_risk_fraction,
        )
    )
    if not sizing.approved:
        return None, sizing.reason

    return (
        ShadowPaperTrade(
            trade_id=(
                f"trailing-research-{candidate.symbol}-"
                f"{candidate.signal_at.isoformat()}"
            ),
            symbol=candidate.symbol,
            mechanism=candidate.mechanism,
            side=candidate.side,
            signal_at=candidate.signal_at,
            entry_bar_at=entry_bar.timestamp,
            opened_at=entry_bar.timestamp,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            spread_at_entry=spread,
            lots=baseline.lots,
            risk_eur=baseline.risk_eur,
            risk_distance=risk_distance,
            target_r=candidate.target_r,
            max_holding_bars=candidate.max_holding_bars,
        ),
        None,
    )


def _comparison(
    baseline: Sequence[TradeOutcome],
    treatment: Sequence[TradeOutcome],
    adjustment_counts: Sequence[int],
    mask: Sequence[bool],
) -> TrailingComparisonWindow:
    static_rows = [row for row, keep in zip(baseline, mask) if keep]
    treatment_rows = [row for row, keep in zip(treatment, mask) if keep]
    adjustments = [count for count, keep in zip(adjustment_counts, mask) if keep]

    static_summary = _summary(static_rows)
    treatment_summary = _summary(treatment_rows)

    improved = sum(
        treated.result_r > static.result_r + 1e-12
        for static, treated in zip(static_rows, treatment_rows)
    )
    worsened = sum(
        treated.result_r < static.result_r - 1e-12
        for static, treated in zip(static_rows, treatment_rows)
    )
    unchanged = len(static_rows) - improved - worsened

    return TrailingComparisonWindow(
        static=static_summary,
        treatment=treatment_summary,
        paired_trades=len(static_rows),
        improved_trades=improved,
        worsened_trades=worsened,
        unchanged_trades=unchanged,
        total_adjustments=sum(adjustments),
        expectancy_delta_r=(
            treatment_summary.expectancy_r - static_summary.expectancy_r
        ),
        max_drawdown_delta_r=(
            treatment_summary.max_drawdown_r - static_summary.max_drawdown_r
        ),
    )
