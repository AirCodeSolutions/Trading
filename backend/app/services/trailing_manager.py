from collections.abc import Sequence
from itertools import pairwise

from app.domain.market import MarketBar
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trailing_manager import (
    TrailingAdjustment,
    TrailingManagerConfig,
    TrailingReplayResult,
)


def propose_trailing_adjustment(
    *,
    trade: ShadowPaperTrade,
    closed_bars: Sequence[MarketBar],
    current_stop: float,
    current_target: float,
    config: TrailingManagerConfig,
) -> TrailingAdjustment | None:
    if len(closed_bars) < max(config.structure_window, 2):
        return None
    last = closed_bars[-1]
    atr = _atr(closed_bars, config.atr_window)
    if atr <= 0:
        return None

    favorable_close_r = _favorable_close_r(trade, last.close)
    stop_after = current_stop
    target_after = current_target
    reasons: list[str] = []

    structure = closed_bars[-config.structure_window :]
    if (
        config.enable_stop_trailing
        and not config.stop_trailing_requires_extended_target
    ):
        stop_after, stop_reasons = _tighten_stop(
            trade=trade,
            structure=structure,
            last=last,
            atr=atr,
            favorable_close_r=favorable_close_r,
            current_stop=stop_after,
            config=config,
        )
        reasons.extend(stop_reasons)

    protected = (
        stop_after >= trade.entry_price
        if trade.side == Side.BUY
        else stop_after <= trade.entry_price
    )
    directional = _directional_closes(structure, trade.side)
    if (
        config.enable_target_extension
        and favorable_close_r >= config.target_extension_activation_r
        and (protected or not config.target_extension_requires_protected_stop)
        and directional
        and config.extended_target_r > trade.target_r
    ):
        extended = (
            trade.entry_price + config.extended_target_r * trade.risk_distance
            if trade.side == Side.BUY
            else trade.entry_price - config.extended_target_r * trade.risk_distance
        )
        if trade.side == Side.BUY and extended > target_after or trade.side == Side.SELL and extended < target_after:
            target_after = extended
            reasons.append("target_extended_on_protected_momentum")

    if (
        config.enable_stop_trailing
        and config.stop_trailing_requires_extended_target
        and target_after != trade.target_price
    ):
        stop_after, stop_reasons = _tighten_stop(
            trade=trade,
            structure=structure,
            last=last,
            atr=atr,
            favorable_close_r=favorable_close_r,
            current_stop=stop_after,
            config=config,
        )
        reasons.extend(stop_reasons)

    if stop_after == current_stop and target_after == current_target:
        return None

    return TrailingAdjustment(
        at=last.timestamp,
        side=trade.side,
        favorable_close_r=favorable_close_r,
        stop_before=current_stop,
        stop_after=stop_after,
        target_before=current_target,
        target_after=target_after,
        atr=atr,
        reason="; ".join(reasons),
    )


def _tighten_stop(
    *,
    trade: ShadowPaperTrade,
    structure: Sequence[MarketBar],
    last: MarketBar,
    atr: float,
    favorable_close_r: float,
    current_stop: float,
    config: TrailingManagerConfig,
) -> tuple[float, list[str]]:
    stop_after = current_stop
    reasons: list[str] = []

    if trade.side == Side.BUY:
        structure_stop = (
            min(bar.low for bar in structure)
            - config.atr_buffer_multiple * atr
        )
        if structure_stop < last.close:
            tightened = max(stop_after, structure_stop, trade.stop_price)
            if tightened > stop_after:
                stop_after = tightened
                reasons.append("structure_stop_tightened")
        if (
            favorable_close_r >= config.break_even_activation_r
            and trade.entry_price < last.close
            and trade.entry_price > stop_after
        ):
            stop_after = trade.entry_price
            reasons.append("break_even_locked")
    else:
        structure_stop = (
            max(bar.high for bar in structure)
            + config.atr_buffer_multiple * atr
        )
        if structure_stop > last.close:
            tightened = min(stop_after, structure_stop, trade.stop_price)
            if tightened < stop_after:
                stop_after = tightened
                reasons.append("structure_stop_tightened")
        if (
            favorable_close_r >= config.break_even_activation_r
            and trade.entry_price > last.close
            and trade.entry_price < stop_after
        ):
            stop_after = trade.entry_price
            reasons.append("break_even_locked")

    return stop_after, reasons


def replay_trailing_trade(
    trade: ShadowPaperTrade,
    bars: Sequence[MarketBar],
    *,
    config: TrailingManagerConfig | None = None,
) -> TrailingReplayResult:
    policy = config or TrailingManagerConfig()
    relevant = [
        bar
        for bar in bars
        if bar.timestamp >= trade.entry_bar_at
    ][: trade.max_holding_bars]
    if not relevant:
        raise ValueError("no replay bars are available for trade")

    current_stop = trade.stop_price
    current_target = trade.target_price
    adjustments: list[TrailingAdjustment] = []
    seen: list[MarketBar] = []

    for index, bar in enumerate(relevant, start=1):
        stop_hit, target_hit = _bar_hits(
            trade,
            bar,
            current_stop=current_stop,
            current_target=current_target,
        )
        # Conservative ordering matches the existing PAPER replay contract.
        if stop_hit:
            result_r = _exit_r(trade, current_stop)
            return _result(
                trade,
                result_r=result_r,
                exit_reason="trailing_stop" if current_stop != trade.stop_price else "stop",
                bars_held=index,
                final_stop=current_stop,
                final_target=current_target,
                adjustments=adjustments,
            )
        if target_hit:
            result_r = _exit_r(trade, current_target)
            return _result(
                trade,
                result_r=result_r,
                exit_reason=(
                    "extended_target"
                    if current_target != trade.target_price
                    else "target"
                ),
                bars_held=index,
                final_stop=current_stop,
                final_target=current_target,
                adjustments=adjustments,
            )

        seen.append(bar)
        adjustment = propose_trailing_adjustment(
            trade=trade,
            closed_bars=seen,
            current_stop=current_stop,
            current_target=current_target,
            config=policy,
        )
        if adjustment is not None:
            _assert_no_added_risk(trade, current_stop, adjustment.stop_after)
            current_stop = adjustment.stop_after
            current_target = adjustment.target_after
            adjustments.append(adjustment)

    last = relevant[-1]
    exit_price = (
        last.close
        if trade.side == Side.BUY
        else last.close + trade.spread_at_entry
    )
    return _result(
        trade,
        result_r=_exit_r(trade, exit_price),
        exit_reason="timeout",
        bars_held=len(relevant),
        final_stop=current_stop,
        final_target=current_target,
        adjustments=adjustments,
    )


def _bar_hits(
    trade: ShadowPaperTrade,
    bar: MarketBar,
    *,
    current_stop: float,
    current_target: float,
) -> tuple[bool, bool]:
    if trade.side == Side.BUY:
        return bar.low <= current_stop, bar.high >= current_target
    ask_high = bar.high + trade.spread_at_entry
    ask_low = bar.low + trade.spread_at_entry
    return ask_high >= current_stop, ask_low <= current_target


def _exit_r(trade: ShadowPaperTrade, exit_price: float) -> float:
    if trade.side == Side.BUY:
        return (exit_price - trade.entry_price) / trade.risk_distance
    return (trade.entry_price - exit_price) / trade.risk_distance


def _favorable_close_r(trade: ShadowPaperTrade, close: float) -> float:
    close_price = close if trade.side == Side.BUY else close + trade.spread_at_entry
    return _exit_r(trade, close_price)


def _directional_closes(bars: Sequence[MarketBar], side: Side) -> bool:
    closes = [bar.close for bar in bars]
    if len(closes) < 2:
        return False
    pairs = pairwise(closes)
    if side == Side.BUY:
        return all(right > left for left, right in pairs)
    return all(right < left for left, right in pairs)


def _atr(bars: Sequence[MarketBar], window: int) -> float:
    sample = bars[-window:]
    if len(sample) < 2:
        return 0.0
    ranges: list[float] = []
    previous_close = sample[0].close
    for bar in sample[1:]:
        ranges.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
        previous_close = bar.close
    return sum(ranges) / len(ranges) if ranges else 0.0


def _assert_no_added_risk(
    trade: ShadowPaperTrade,
    stop_before: float,
    stop_after: float,
) -> None:
    if trade.side == Side.BUY and stop_after < stop_before:
        raise ValueError("trailing manager cannot widen BUY stop")
    if trade.side == Side.SELL and stop_after > stop_before:
        raise ValueError("trailing manager cannot widen SELL stop")
    initial_loss_distance = trade.risk_distance
    new_loss_distance = (
        max(0.0, trade.entry_price - stop_after)
        if trade.side == Side.BUY
        else max(0.0, stop_after - trade.entry_price)
    )
    if new_loss_distance > initial_loss_distance + 1e-12:
        raise ValueError("trailing manager cannot increase initial monetary risk")


def _result(
    trade: ShadowPaperTrade,
    *,
    result_r: float,
    exit_reason: str,
    bars_held: int,
    final_stop: float,
    final_target: float,
    adjustments: list[TrailingAdjustment],
) -> TrailingReplayResult:
    return TrailingReplayResult(
        result_r=result_r,
        pnl_eur=result_r * trade.risk_eur,
        exit_reason=exit_reason,
        bars_held=bars_held,
        final_stop=final_stop,
        final_target=final_target,
        adjustments=adjustments,
        maximum_added_risk_r=0.0,
    )
