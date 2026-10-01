from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.market import MarketBar
from app.domain.position_manager import (
    PositionManagerAggregate,
    PositionManagerComparison,
    PositionManagerReport,
    PositionManagerV2Action,
    PositionManagerV2Snapshot,
    PositionManagerV2State,
)
from app.domain.regime import MarketRegime
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trailing_manager import TrailingManagerConfig
from app.services.replay import RegimeReplay
from app.services.shadow_paper import _next_full_m5_bar_start, resolve_open_trade
from app.services.trailing_manager import (
    _assert_no_added_risk,
    _bar_hits,
    _directional_closes,
    _exit_r,
    _favorable_close_r,
    propose_trailing_adjustment,
)


def _landmark_beyond_target(trade: ShadowPaperTrade, target: float | None = None) -> tuple[str | None, float | None]:
    context = trade.session_landmark_context
    if context is None:
        return None, None
    target = trade.target_price if target is None else target
    values = (
        ("previous_day_high", context.previous_day_high), ("previous_day_low", context.previous_day_low),
        ("asia_high", context.asia_high), ("asia_low", context.asia_low),
        ("london_high_so_far", context.london_high_so_far), ("london_low_so_far", context.london_low_so_far),
        ("us_high_so_far", context.us_high_so_far), ("us_low_so_far", context.us_low_so_far),
    )
    candidates = [item for item in values if item[1] is not None and (
        trade.side is Side.BUY and item[1] > target or trade.side is Side.SELL and item[1] < target)]
    return (min(candidates, key=lambda item: abs(item[1] - target)) if candidates else (None, None))


def _m15_at(at: datetime, bars: Sequence[MarketBar], regimes: Sequence[object]) -> tuple[str | None, int | None]:
    selected = None
    for bar, regime in zip(bars, regimes):
        if bar.timestamp + timedelta(minutes=15) <= at:
            selected = regime
    if selected is None:
        return None, None
    return getattr(selected, "regime", None), getattr(selected, "direction", None)


def _baseline_trade(trade: ShadowPaperTrade) -> ShadowPaperTrade:
    return trade.model_copy(update={"status": PaperTradeStatus.OPEN, "exit_at": None, "exit_price": None, "result_r": None, "pnl_eur": None, "bars_held": 0})


def _mfe_mae(trade: ShadowPaperTrade, bar: MarketBar) -> tuple[float, float]:
    if trade.side is Side.BUY:
        return max(0.0, (bar.high - trade.entry_price) / trade.risk_distance), max(0.0, (trade.entry_price - bar.low) / trade.risk_distance)
    return max(0.0, (trade.entry_price - (bar.low + trade.spread_at_entry)) / trade.risk_distance), max(0.0, ((bar.high + trade.spread_at_entry) - trade.entry_price) / trade.risk_distance)


def _excursions(trade: ShadowPaperTrade, bars: Sequence[MarketBar]) -> tuple[float, float]:
    mfe = mae = 0.0
    for bar in bars:
        bar_mfe, bar_mae = _mfe_mae(trade, bar)
        mfe, mae = max(mfe, bar_mfe), max(mae, bar_mae)
    return mfe, mae


def replay_position_manager_v2(
    trade: ShadowPaperTrade,
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar] = (),
    *,
    config: TrailingManagerConfig | None = None,
) -> tuple[PositionManagerV2Snapshot | None, PositionManagerComparison]:
    policy = config or TrailingManagerConfig()
    baseline = resolve_open_trade(_baseline_trade(trade), bars_m5)
    first_full = _next_full_m5_bar_start(trade.opened_at)
    relevant = sorted((bar for bar in bars_m5 if bar.timestamp >= first_full), key=lambda bar: bar.timestamp)[:trade.max_holding_bars]
    empty = PositionManagerComparison(trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, pending=True)
    if not relevant:
        snapshot = PositionManagerV2Snapshot(
            trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, side=trade.side,
            evaluated_at=trade.opened_at, state=PositionManagerV2State.INITIAL_RISK, entry_price=trade.entry_price,
            initial_stop=trade.stop_price, current_stop=trade.stop_price, initial_target=trade.target_price,
            current_target=trade.target_price, initial_risk_distance=trade.risk_distance, risk_eur=trade.risk_eur,
            bars_held=0, favorable_close_r=0.0, mfe_r=0.0, mae_r=0.0, current_result_r=0.0,
            protected=False, proposed_action=PositionManagerV2Action.HOLD, reason="no complete M5 bar available",
        )
        return snapshot, empty

    regimes = RegimeReplay(max_history=max(50, len(bars_m15))).replay(sorted(bars_m15, key=lambda b: b.timestamp)) if bars_m15 else []
    current_stop, current_target = trade.stop_price, trade.target_price
    seen: list[MarketBar] = []
    mfe = mae = 0.0
    state, action, reason = PositionManagerV2State.INITIAL_RISK, PositionManagerV2Action.HOLD, "initial risk unchanged"
    protected = extension_used = no_follow = regime_loss = False
    exit_r = exit_reason = None
    exit_bars = 0
    m15_regime = m15_direction = None
    landmark_type, landmark_price = _landmark_beyond_target(trade)
    candidate_stop = candidate_target = None
    trailing_policy = policy.model_copy(update={"enable_target_extension": False})

    for index, bar in enumerate(relevant, start=1):
        action = PositionManagerV2Action.HOLD
        candidate_stop = candidate_target = None
        stop_hit, target_hit = _bar_hits(trade, bar, current_stop=current_stop, current_target=current_target)
        if stop_hit or target_hit:
            bar_mfe, bar_mae = _mfe_mae(trade, bar)
            mfe, mae = max(mfe, bar_mfe), max(mae, bar_mae)
            exit_r = _exit_r(trade, current_stop if stop_hit else current_target)
            exit_reason = "stop" if stop_hit else "target"
            exit_bars = index
            state = PositionManagerV2State.CLOSED_STOP if stop_hit else PositionManagerV2State.CLOSED_TARGET
            action = PositionManagerV2Action.CLOSED_STOP if stop_hit else PositionManagerV2Action.CLOSED_TARGET
            reason = "conservative stop-first resolution" if stop_hit else "active target reached"
            break

        seen.append(bar)
        bar_mfe, bar_mae = _mfe_mae(trade, bar)
        mfe, mae = max(mfe, bar_mfe), max(mae, bar_mae)
        close_r = _favorable_close_r(trade, bar.close)
        m15_regime, m15_direction = _m15_at(bar.timestamp + timedelta(minutes=5), bars_m15, regimes)
        opposite = m15_regime == MarketRegime.DIRECTIONAL and ((trade.side is Side.BUY and (m15_direction or 0) < 0) or (trade.side is Side.SELL and (m15_direction or 0) > 0))
        if opposite:
            exit_r, exit_reason, exit_bars = _exit_r(trade, bar.close if trade.side is Side.BUY else bar.close + trade.spread_at_entry), "regime_loss", index
            state, action, reason = PositionManagerV2State.REGIME_LOSS_EXIT, PositionManagerV2Action.EXIT_REGIME_LOSS, "opposite directional M15 regime"
            regime_loss = True
            break

        favorable_closes = [_favorable_close_r(trade, item.close) for item in seen]
        if index >= policy.structure_window and max(favorable_closes) <= 0:
            exit_r, exit_reason, exit_bars = _exit_r(trade, bar.close if trade.side is Side.BUY else bar.close + trade.spread_at_entry), "no_follow_through", index
            state, action, reason = PositionManagerV2State.NO_FOLLOW_THROUGH, PositionManagerV2Action.EXIT_NO_FOLLOW_THROUGH, "no favorable close after structure window"
            no_follow = True
            break

        eligible_for_protection = close_r >= policy.break_even_activation_r
        adjustment = propose_trailing_adjustment(trade=trade, closed_bars=seen, current_stop=current_stop, current_target=current_target, config=trailing_policy)
        if adjustment is not None and adjustment.stop_after != current_stop:
            _assert_no_added_risk(trade, current_stop, adjustment.stop_after)
            candidate_stop, current_stop = adjustment.stop_after, adjustment.stop_after
            action = PositionManagerV2Action.TIGHTEN_STOP
            reason = adjustment.reason
        protected = current_stop >= trade.entry_price if trade.side is Side.BUY else current_stop <= trade.entry_price
        if protected:
            state = PositionManagerV2State.PROTECT if eligible_for_protection else state
        if protected and len(seen) >= policy.structure_window and _directional_closes(seen[-policy.structure_window:], trade.side):
            landmark_type, landmark_price = _landmark_beyond_target(trade, current_target)
            if landmark_price is not None:
                candidate_target, current_target = landmark_price, landmark_price
                extension_used = True
                state, action, reason = PositionManagerV2State.EXTEND, PositionManagerV2Action.EXTEND_TARGET, "protected directional structure extended to captured landmark"
        exit_bars = index

    if exit_r is None and len(relevant) == trade.max_holding_bars:
        last = relevant[-1]
        exit_price = last.close if trade.side is Side.BUY else last.close + trade.spread_at_entry
        exit_r, exit_reason, exit_bars = _exit_r(trade, exit_price), "safety_timeout", len(relevant)
        state, action, reason = PositionManagerV2State.SAFETY_TIMEOUT, PositionManagerV2Action.EXIT_SAFETY_TIMEOUT, "max_holding_bars safety timeout"
    pending = exit_r is None
    mark_price = relevant[min(exit_bars, len(relevant)) - 1].close if exit_bars else relevant[-1].close
    current_result = _exit_r(trade, mark_price if trade.side is Side.BUY else mark_price + trade.spread_at_entry) if pending else exit_r
    baseline_result = baseline.result_r
    baseline_bars = relevant[:baseline.bars_held]
    baseline_mfe, baseline_mae = _excursions(trade, baseline_bars)
    v2_bars = relevant[:exit_bars] if not pending else relevant
    v2_mfe, v2_mae = _excursions(trade, v2_bars)
    invalid = False
    invalid_reason = None
    if trade.status is not PaperTradeStatus.OPEN:
        status_matches = {
            PaperTradeStatus.STOP: "stop", PaperTradeStatus.TARGET: "target", PaperTradeStatus.TIMEOUT: "timeout",
        }
        result_mismatch = baseline_result is not None and trade.result_r is not None and abs(baseline_result - trade.result_r) > 1e-9
        status_mismatch = status_matches.get(trade.status) != baseline.status.value
        bars_mismatch = trade.bars_held != baseline.bars_held
        if result_mismatch or status_mismatch or bars_mismatch:
            invalid, invalid_reason = True, "persisted PAPER result differs from causal baseline replay"
    comparison = PositionManagerComparison(
        trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism,
        baseline_result_r=baseline_result, v2_result_r=None if pending else exit_r,
        delta_r=None if pending or baseline_result is None else exit_r - baseline_result,
        baseline_exit_reason=baseline.status.value, v2_exit_reason=exit_reason, mfe_r=v2_mfe, mae_r=v2_mae,
        baseline_mfe_r=baseline_mfe, baseline_mae_r=baseline_mae, v2_mfe_r=v2_mfe, v2_mae_r=v2_mae,
        baseline_mfe_capture=baseline_result / baseline_mfe if baseline_result is not None and baseline_mfe > 0 else None,
        v2_mfe_capture=exit_r / v2_mfe if not pending and v2_mfe > 0 else None,
        baseline_giveback_r=max(0.0, baseline_mfe - baseline_result) if baseline_result is not None else None,
        v2_giveback_r=max(0.0, v2_mfe - exit_r) if not pending else None,
        bars_held_baseline=baseline.bars_held, bars_held_v2=None if pending else exit_bars,
        protected_before_exit=protected, extension_used=extension_used, no_follow_through_used=no_follow,
        regime_loss_used=regime_loss, pending=pending, invalid_data=invalid, invalid_reason=invalid_reason,
    )
    last = relevant[min(exit_bars, len(relevant)) - 1] if exit_bars else relevant[-1]
    snapshot = PositionManagerV2Snapshot(
        trade_id=trade.trade_id, symbol=trade.symbol, mechanism=trade.mechanism, side=trade.side,
        evaluated_at=last.timestamp, state=state, entry_price=trade.entry_price, initial_stop=trade.stop_price,
        current_stop=current_stop, candidate_stop=candidate_stop, initial_target=trade.target_price,
        current_target=current_target, candidate_target=candidate_target, initial_risk_distance=trade.risk_distance,
        risk_eur=trade.risk_eur, bars_held=exit_bars, favorable_close_r=_favorable_close_r(trade, last.close),
        mfe_r=v2_mfe, mae_r=v2_mae, current_result_r=current_result, protected=protected,
        landmark_type=landmark_type, landmark_price=landmark_price, proposed_action=action,
        proposed_exit_price=None if pending else (trade.entry_price + exit_r * trade.risk_distance if trade.side is Side.BUY else trade.entry_price - exit_r * trade.risk_distance),
        proposed_exit_r=None if pending else exit_r, reason=reason, m15_regime=m15_regime, m15_direction=m15_direction,
        maximum_added_risk_r=0.0,
    )
    if invalid:
        comparison.pending = False
    return snapshot, comparison


def _profit_factor(values: Sequence[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return 99.0 if gains > 0 and losses == 0 else gains / losses if losses else 0.0


def _drawdown(values: Sequence[float]) -> float:
    equity = peak = dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return dd


def _aggregate(items: Sequence[PositionManagerComparison]) -> PositionManagerAggregate:
    valid = [item for item in items if not item.pending and not item.invalid_data and item.v2_result_r is not None]
    baseline = [item.baseline_result_r for item in valid if item.baseline_result_r is not None]
    v2 = [item.v2_result_r for item in valid if item.v2_result_r is not None]
    captures = [item.v2_mfe_capture for item in valid if item.v2_mfe_capture is not None]
    return PositionManagerAggregate(
        trades=len(valid), baseline_total_r=sum(baseline), v2_total_r=sum(v2), delta_r=sum(v2)-sum(baseline),
        baseline_expectancy_r=sum(baseline)/len(baseline) if baseline else 0.0, v2_expectancy_r=sum(v2)/len(v2) if v2 else 0.0,
        baseline_profit_factor=_profit_factor(baseline), v2_profit_factor=_profit_factor(v2),
        baseline_max_drawdown_r=_drawdown(baseline), v2_max_drawdown_r=_drawdown(v2),
        average_giveback_r=sum(item.v2_giveback_r or 0 for item in valid)/len(valid) if valid else 0.0,
        average_mfe_capture=sum(captures)/len(captures) if captures else None,
    )


def build_position_manager_report(
    trades: Sequence[ShadowPaperTrade],
    bars_by_symbol: dict[str, Sequence[MarketBar]],
    *, now: datetime, window_hours: int, bars_by_symbol_m15: dict[str, Sequence[MarketBar]] | None = None,
) -> PositionManagerReport:
    comparisons: list[PositionManagerComparison] = []
    for trade in sorted(trades, key=lambda item: (item.opened_at, item.trade_id)):
        if (now - trade.opened_at).total_seconds() <= window_hours * 3600:
            _, comparison = replay_position_manager_v2(trade, bars_by_symbol.get(trade.symbol, ()), (bars_by_symbol_m15 or {}).get(trade.symbol, ()))
            comparisons.append(comparison)
    valid = [item for item in comparisons if not item.pending and not item.invalid_data and item.v2_result_r is not None]
    baseline = [item.baseline_result_r for item in valid if item.baseline_result_r is not None]
    v2 = [item.v2_result_r for item in valid if item.v2_result_r is not None]
    captures_b = [item.baseline_mfe_capture for item in valid if item.baseline_mfe_capture is not None]
    captures_v = [item.v2_mfe_capture for item in valid if item.v2_mfe_capture is not None]
    return PositionManagerReport(
        window_hours=window_hours, generated_at=now, trades=len(valid), pending=sum(item.pending for item in comparisons), invalid=sum(item.invalid_data for item in comparisons), comparisons=comparisons,
        baseline_total_r=sum(baseline), v2_total_r=sum(v2), delta_r=sum(v2)-sum(baseline), baseline_expectancy_r=sum(baseline)/len(baseline) if baseline else 0.0, v2_expectancy_r=sum(v2)/len(v2) if v2 else 0.0,
        baseline_max_drawdown_r=_drawdown(baseline), v2_max_drawdown_r=_drawdown(v2), baseline_profit_factor=_profit_factor(baseline), v2_profit_factor=_profit_factor(v2),
        baseline_average_mfe_capture=sum(captures_b)/len(captures_b) if captures_b else None, v2_average_mfe_capture=sum(captures_v)/len(captures_v) if captures_v else None,
        baseline_average_giveback_r=sum(item.baseline_giveback_r or 0 for item in valid)/len(valid) if valid else 0.0, v2_average_giveback_r=sum(item.v2_giveback_r or 0 for item in valid)/len(valid) if valid else 0.0,
        no_follow_through_count=sum(item.no_follow_through_used for item in valid), extension_count=sum(item.extension_used for item in valid), regime_loss_count=sum(item.regime_loss_used for item in valid),
        by_asset={key: _aggregate([item for item in comparisons if item.symbol == key]) for key in sorted({item.symbol for item in comparisons})},
        by_mechanism={key: _aggregate([item for item in comparisons if item.mechanism.value == key]) for key in sorted({item.mechanism.value for item in comparisons})},
    )
