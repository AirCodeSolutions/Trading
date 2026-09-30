from collections.abc import Sequence
from datetime import datetime

from app.domain.market import MarketBar
from app.domain.position_manager import (
    PositionManagerComparison,
    PositionManagerReport,
    PositionManagerV2Action,
    PositionManagerV2Snapshot,
    PositionManagerV2State,
)
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trailing_manager import TrailingManagerConfig
from app.services.shadow_paper import (
    resolve_open_trade,
)
from app.services.trailing_manager import (
    _assert_no_added_risk,
    _bar_hits,
    _exit_r,
    _favorable_close_r,
    propose_trailing_adjustment,
)


def _landmark_beyond_target(trade: ShadowPaperTrade) -> tuple[str | None, float | None]:
    context = trade.session_landmark_context
    if context is None:
        return None, None
    values = (
        ("previous_day_high", context.previous_day_high),
        ("previous_day_low", context.previous_day_low),
        ("asia_high", context.asia_high),
        ("asia_low", context.asia_low),
        ("london_high_so_far", context.london_high_so_far),
        ("london_low_so_far", context.london_low_so_far),
        ("us_high_so_far", context.us_high_so_far),
        ("us_low_so_far", context.us_low_so_far),
    )
    candidates = [
        item for item in values
        if item[1] is not None
        and ((trade.side is Side.BUY and item[1] > trade.target_price) or (trade.side is Side.SELL and item[1] < trade.target_price))
    ]
    if not candidates:
        return None, None
    return min(candidates, key=lambda item: abs(item[1] - trade.target_price))


def replay_position_manager_v2(
    trade: ShadowPaperTrade,
    bars_m5: Sequence[MarketBar],
    *,
    config: TrailingManagerConfig | None = None,
) -> tuple[PositionManagerV2Snapshot | None, PositionManagerComparison]:
    policy = config or TrailingManagerConfig()
    baseline = resolve_open_trade(trade, bars_m5)
    relevant = [bar for bar in bars_m5 if bar.timestamp >= trade.entry_bar_at][: trade.max_holding_bars]
    if not relevant:
        return None, PositionManagerComparison(trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, pending=True)
    current_stop = trade.stop_price
    current_target = trade.target_price
    seen: list[MarketBar] = []
    mfe = float("-inf")
    mae = float("inf")
    state = PositionManagerV2State.INITIAL_RISK
    action = PositionManagerV2Action.HOLD
    reason = "initial risk unchanged"
    protected = False
    extension_used = False
    no_follow = False
    exit_r: float | None = None
    exit_reason: str | None = None
    exit_bars = 0
    landmark_type, landmark_price = _landmark_beyond_target(trade)

    for index, bar in enumerate(relevant, start=1):
        stop_hit, target_hit = _bar_hits(trade, bar, current_stop=current_stop, current_target=current_target)
        if stop_hit:
            exit_r, exit_reason, exit_bars = _exit_r(trade, current_stop), "stop", index
            state, action, reason = PositionManagerV2State.CLOSED_STOP, PositionManagerV2Action.CLOSED_STOP, "conservative stop-first resolution"
            break
        if target_hit:
            if protected and landmark_price is not None:
                current_target = landmark_price
                state, action, reason = PositionManagerV2State.EXTEND, PositionManagerV2Action.EXTEND_TARGET, "protected target extended to captured landmark"
                extension_used = True
            else:
                exit_r, exit_reason, exit_bars = _exit_r(trade, current_target), "target", index
                state, action, reason = PositionManagerV2State.CLOSED_TARGET, PositionManagerV2Action.CLOSED_TARGET, "baseline target reached"
                break

        seen.append(bar)
        close_r = _favorable_close_r(trade, bar.close)
        favorable = max(0.0, close_r)
        adverse = _exit_r(trade, bar.low if trade.side is Side.BUY else bar.high + trade.spread_at_entry)
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)
        if index >= policy.structure_window and max(_favorable_close_r(trade, item.close) for item in seen[-policy.structure_window:]) <= 0 and mfe <= 0:
            exit_r, exit_reason, exit_bars = _exit_r(trade, bar.close if trade.side is Side.BUY else bar.close + trade.spread_at_entry), "no_follow_through", index
            state, action, reason = PositionManagerV2State.NO_FOLLOW_THROUGH, PositionManagerV2Action.EXIT_NO_FOLLOW_THROUGH, "no favorable close after structure window"
            no_follow = True
            break
        if close_r >= policy.break_even_activation_r:
            protected = True
            state = PositionManagerV2State.PROTECT
        adjustment = propose_trailing_adjustment(trade=trade, closed_bars=seen, current_stop=current_stop, current_target=current_target, config=policy)
        if adjustment is not None:
            _assert_no_added_risk(trade, current_stop, adjustment.stop_after)
            if adjustment.stop_after != current_stop:
                current_stop = adjustment.stop_after
                state = PositionManagerV2State.TRAIL if protected else PositionManagerV2State.PROTECT
                action, reason = PositionManagerV2Action.TIGHTEN_STOP, adjustment.reason
            current_target = adjustment.target_after

        PositionManagerV2Snapshot(
            trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, side=trade.side,
            evaluated_at=bar.timestamp, state=state, entry_price=trade.entry_price,
            initial_stop=trade.stop_price, current_stop=current_stop, candidate_stop=current_stop,
            initial_target=trade.target_price, current_target=current_target, candidate_target=current_target,
            initial_risk_distance=trade.risk_distance, risk_eur=trade.risk_eur, bars_held=index,
            favorable_close_r=close_r, mfe_r=max(mfe, 0.0), mae_r=mae if mae != float("inf") else 0.0,
            current_result_r=_exit_r(trade, bar.close if trade.side is Side.BUY else bar.close + trade.spread_at_entry),
            protected=protected, landmark_type=landmark_type, landmark_price=landmark_price,
            proposed_action=action, reason=reason,
        )

    if exit_r is None:
        last = relevant[-1]
        exit_price = last.close if trade.side is Side.BUY else last.close + trade.spread_at_entry
        exit_r, exit_reason, exit_bars = _exit_r(trade, exit_price), "safety_timeout", len(relevant)
        state, action, reason = PositionManagerV2State.SAFETY_TIMEOUT, PositionManagerV2Action.EXIT_SAFETY_TIMEOUT, "max_holding_bars safety timeout"
    baseline_r = baseline.result_r
    final_mfe = max(mfe, 0.0)
    v2_capture = exit_r / final_mfe if final_mfe > 0 else None
    baseline_capture = baseline_r / final_mfe if baseline_r is not None and final_mfe > 0 else None
    comparison = PositionManagerComparison(
        trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism,
        baseline_result_r=baseline_r, v2_result_r=exit_r, delta_r=exit_r - baseline_r if baseline_r is not None else None,
        baseline_exit_reason=baseline.status.value, v2_exit_reason=exit_reason, mfe_r=final_mfe,
        mae_r=mae if mae != float("inf") else 0.0, baseline_mfe_capture=baseline_capture, v2_mfe_capture=v2_capture,
        baseline_giveback_r=max(0.0, final_mfe - baseline_r) if baseline_r is not None else None,
        v2_giveback_r=max(0.0, final_mfe - exit_r), bars_held_baseline=baseline.bars_held, bars_held_v2=exit_bars,
        protected_before_exit=protected, extension_used=extension_used, no_follow_through_used=no_follow,
    )
    snapshot = PositionManagerV2Snapshot(
        trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, side=trade.side,
        evaluated_at=relevant[-1].timestamp, state=state, entry_price=trade.entry_price, initial_stop=trade.stop_price,
        current_stop=current_stop, candidate_stop=current_stop, initial_target=trade.target_price,
        current_target=current_target, candidate_target=current_target, initial_risk_distance=trade.risk_distance,
        risk_eur=trade.risk_eur, bars_held=exit_bars, favorable_close_r=_favorable_close_r(trade, relevant[-1].close),
        mfe_r=final_mfe, mae_r=mae if mae != float("inf") else 0.0,
        current_result_r=exit_r, protected=protected, landmark_type=landmark_type, landmark_price=landmark_price,
        proposed_action=action, proposed_exit_price=trade.entry_price + exit_r * trade.risk_distance if trade.side is Side.BUY else trade.entry_price - exit_r * trade.risk_distance,
        proposed_exit_r=exit_r, reason=reason,
    )
    return snapshot, comparison


def build_position_manager_report(
    trades: Sequence[ShadowPaperTrade],
    bars_by_symbol: dict[str, Sequence[MarketBar]],
    *,
    now: datetime,
    window_hours: int,
) -> PositionManagerReport:
    comparisons: list[PositionManagerComparison] = []
    for trade in trades:
        if (now - trade.opened_at).total_seconds() > window_hours * 3600:
            continue
        _, comparison = replay_position_manager_v2(trade, bars_by_symbol.get(trade.symbol, ()))
        comparisons.append(comparison)
    resolved = [item for item in comparisons if not item.pending and item.v2_result_r is not None]
    baseline = [item.baseline_result_r for item in resolved if item.baseline_result_r is not None]
    v2 = [item.v2_result_r for item in resolved if item.v2_result_r is not None]
    def dd(values: list[float]) -> float:
        equity = peak = drawdown = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return drawdown
    captures_b = [item.baseline_mfe_capture for item in resolved if item.baseline_mfe_capture is not None]
    captures_v = [item.v2_mfe_capture for item in resolved if item.v2_mfe_capture is not None]
    return PositionManagerReport(
        window_hours=window_hours, generated_at=now, trades=len(resolved), pending=len(comparisons) - len(resolved), comparisons=comparisons,
        baseline_total_r=sum(baseline), v2_total_r=sum(v2), delta_r=sum(v2) - sum(baseline),
        baseline_expectancy_r=sum(baseline) / len(baseline) if baseline else 0.0,
        v2_expectancy_r=sum(v2) / len(v2) if v2 else 0.0,
        baseline_max_drawdown_r=dd(baseline), v2_max_drawdown_r=dd(v2),
        baseline_average_mfe_capture=sum(captures_b) / len(captures_b) if captures_b else None,
        v2_average_mfe_capture=sum(captures_v) / len(captures_v) if captures_v else None,
        baseline_average_giveback_r=sum(item.baseline_giveback_r or 0 for item in resolved) / len(resolved) if resolved else 0.0,
        v2_average_giveback_r=sum(item.v2_giveback_r or 0 for item in resolved) / len(resolved) if resolved else 0.0,
    )
