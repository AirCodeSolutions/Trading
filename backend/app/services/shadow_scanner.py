from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest
from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.opportunity_strategies import _atr_series
from app.services.replay import RegimeReplay
from app.services.session_continuity import reopen_warmup_remaining

VOLATILITY_PERCENTILE_LOOKBACK = 500
MAX_SNAPSHOT_AGE = timedelta(minutes=10)


def scan_shadow_opportunity(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    spec: BrokerSymbolSpec,
    mechanism: OpportunityMechanism,
    evaluated_at: datetime,
) -> ShadowOpportunityDiagnostic:
    symbol = spec.symbol.upper()
    if len(bars_m5) < 30 or len(bars_m15) < 50:
        raise ValueError("insufficient M5/M15 closed bars for shadow scan")
    if evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    if {bar.symbol.upper() for bar in bars_m5} != {symbol}:
        raise ValueError("M5 bars do not match broker symbol")
    if {bar.symbol.upper() for bar in bars_m15} != {symbol}:
        raise ValueError("M15 bars do not match broker symbol")

    snapshots = RegimeReplay(max_history=600).replay(bars_m15)
    m15_close_times = [bar.timestamp + timedelta(minutes=15) for bar in bars_m15]
    latest_m5 = bars_m5[-1]
    signal_close = latest_m5.timestamp + timedelta(minutes=5)
    regime_index = bisect_right(m15_close_times, signal_close) - 1
    if regime_index < 0:
        raise ValueError("no causal M15 regime available for latest M5 close")
    regime = snapshots[regime_index]
    atr_m5 = _atr_series(bars_m5)

    volatility_percentile = _causal_percentile(
        [item.atr_ratio for item in snapshots],
        regime_index,
    )
    momentum_12_atr = _momentum_12_atr(bars_m15, regime, regime_index)
    base_payload = {
        "symbol": symbol,
        "mechanism": mechanism,
        "evaluated_at": evaluated_at,
        "latest_closed_m5_at": latest_m5.timestamp,
        "latest_closed_m15_at": bars_m15[regime_index].timestamp,
        "regime": regime.regime,
        "regime_direction": regime.direction,
        "atr_m15": regime.atr,
        "atr_ratio": regime.atr_ratio,
        "volatility_percentile": volatility_percentile,
        "momentum_12_atr": momentum_12_atr,
        "efficiency": regime.efficiency,
    }

    warmup_remaining = reopen_warmup_remaining(bars_m5)
    if warmup_remaining > 0:
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason=(
                "session reopen warmup: "
                f"{warmup_remaining} closed M5 bar(s) remaining"
            ),
        )

    snapshot_age = evaluated_at - signal_close
    if snapshot_age > MAX_SNAPSHOT_AGE or snapshot_age < -timedelta(minutes=1):
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason="latest M5 snapshot is stale or timestamp-inconsistent",
        )

    previous_regime = snapshots[regime_index - 1] if regime_index >= 1 else None
    is_new_m15_close = signal_close == m15_close_times[regime_index]
    signal = _detect_signal(
        bars_m5,
        atr_m5,
        regime,
        previous_regime,
        is_new_m15_close,
        mechanism,
    )
    if signal is None:
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason=_no_signal_reason(regime, mechanism),
        )

    (
        side,
        raw_stop,
        target_r,
        max_holding_bars,
        stop_atr,
        break_strength,
        retest_depth,
        reclaim,
        close_location,
        reason,
    ) = signal

    entry = spec.ask if side == Side.BUY else spec.bid
    if mechanism == OpportunityMechanism.DIRECTIONAL_TRANSITION:
        if side == Side.BUY:
            structural_stop = entry - stop_atr
        else:
            structural_stop = entry + stop_atr + spec.spread
    elif side == Side.BUY:
        structural_stop = min(raw_stop, entry - stop_atr)
    else:
        structural_stop = max(raw_stop + spec.spread, entry + stop_atr)

    base_sizing = _sizing_snapshot(
        spec,
        entry,
        structural_stop,
        settings.risk_per_trade_fraction,
    )
    max_sizing = _sizing_snapshot(
        spec,
        entry,
        structural_stop,
        settings.absolute_max_risk_fraction,
    )
    state = (
        ShadowSignalState.SIGNAL_EXECUTABLE
        if base_sizing.approved
        else ShadowSignalState.SIGNAL_BLOCKED
    )
    final_reason = (
        reason
        if base_sizing.approved
        else f"{reason}; base-risk execution blocked: {base_sizing.reason}"
    )

    return ShadowOpportunityDiagnostic(
        **base_payload,
        state=state,
        side=side,
        break_strength_atr_m5=break_strength,
        retest_depth_atr_m5=retest_depth,
        reclaim_atr_m5=reclaim,
        signal_close_location=close_location,
        structural_stop=structural_stop,
        target_r=target_r,
        max_holding_bars=max_holding_bars,
        base_risk=base_sizing,
        max_risk=max_sizing,
        reason=final_reason,
    )


def _detect_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
    previous_regime: RegimeSnapshot | None,
    is_new_m15_close: bool,
    mechanism: OpportunityMechanism,
) -> tuple[
    Side,
    float,
    float,
    int,
    float,
    float | None,
    float | None,
    float | None,
    float | None,
    str,
] | None:
    if mechanism == OpportunityMechanism.BREAK_RETEST_REACCEL:
        return _break_retest_signal(bars, atr, regime)
    if mechanism == OpportunityMechanism.FAILED_AUCTION_REVERSAL:
        return _failed_auction_signal(bars, atr, regime)
    if mechanism == OpportunityMechanism.POST_SHOCK_CONTINUATION:
        return _post_shock_signal(bars, regime)
    if mechanism == OpportunityMechanism.DIRECTIONAL_TRANSITION:
        return _directional_transition_signal(
            bars,
            regime,
            previous_regime,
            is_new_m15_close,
        )
    return None


def _directional_transition_signal(
    bars: Sequence[MarketBar],
    regime: RegimeSnapshot,
    previous_regime: RegimeSnapshot | None,
    is_new_m15_close: bool,
):
    if (
        not is_new_m15_close
        or previous_regime is None
        or regime.regime != MarketRegime.DIRECTIONAL
        or regime.direction == 0
        or regime.atr <= 0
    ):
        return None
    if (
        previous_regime.regime == MarketRegime.DIRECTIONAL
        and previous_regime.direction == regime.direction
    ):
        return None

    bar = bars[-1]
    side = Side.BUY if regime.direction > 0 else Side.SELL
    raw_stop = bar.low if side == Side.BUY else bar.high
    return (
        side,
        raw_stop,
        1.8,
        18,
        0.80 * regime.atr,
        None,
        None,
        None,
        None,
        "first causal M15 transition into directional expansion",
    )


def _break_retest_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
):
    if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
        return None

    index = len(bars) - 1
    bar = bars[index]
    value = atr[index]
    base = bars[index - 15 : index - 3]
    recent = bars[index - 3 : index]
    if value <= 0 or not base or not recent:
        return None

    prior_high = max(item.high for item in base)
    prior_low = min(item.low for item in base)
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return None
    close_location = (bar.close - bar.low) / bar_range

    if regime.direction > 0:
        breakout = max(item.close for item in recent) > prior_high + 0.05 * value
        retest = (
            bar.low <= prior_high + 0.30 * value
            and bar.close > prior_high
            and bar.close > bar.open
            and close_location >= 0.60
        )
        if not (breakout and retest):
            return None
        return (
            Side.BUY,
            bar.low - 0.10 * value,
            1.8,
            18,
            0.65 * value,
            (max(item.close for item in recent) - prior_high) / value,
            (prior_high - bar.low) / value,
            (bar.close - prior_high) / value,
            close_location,
            "directional M15 with M5 break, retest and re-acceleration",
        )

    breakout = min(item.close for item in recent) < prior_low - 0.05 * value
    retest = (
        bar.high >= prior_low - 0.30 * value
        and bar.close < prior_low
        and bar.close < bar.open
        and close_location <= 0.40
    )
    if not (breakout and retest):
        return None
    return (
        Side.SELL,
        bar.high + 0.10 * value,
        1.8,
        18,
        0.65 * value,
        (prior_low - min(item.close for item in recent)) / value,
        (bar.high - prior_low) / value,
        (prior_low - bar.close) / value,
        close_location,
        "directional M15 with M5 break, retest and re-acceleration",
    )


def _failed_auction_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
):
    if regime.regime != MarketRegime.BALANCED:
        return None

    index = len(bars) - 1
    bar = bars[index]
    value = atr[index]
    history = bars[index - 24 : index]
    if value <= 0 or not history:
        return None

    prior_high = max(item.high for item in history)
    prior_low = min(item.low for item in history)
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return None
    upper_wick = bar.high - max(bar.open, bar.close)
    lower_wick = min(bar.open, bar.close) - bar.low
    close_location = (bar.close - bar.low) / bar_range

    if (
        bar.high > prior_high + 0.10 * value
        and bar.close < prior_high - 0.02 * value
        and upper_wick / bar_range >= 0.35
        and close_location <= 0.50
    ):
        return (
            Side.SELL,
            bar.high + 0.15 * value,
            1.5,
            12,
            0.60 * value,
            None,
            None,
            (prior_high - bar.close) / value,
            close_location,
            "balanced M15 with failed upper auction and causal reclaim",
        )

    if (
        bar.low < prior_low - 0.10 * value
        and bar.close > prior_low + 0.02 * value
        and lower_wick / bar_range >= 0.35
        and close_location >= 0.50
    ):
        return (
            Side.BUY,
            bar.low - 0.15 * value,
            1.5,
            12,
            0.60 * value,
            None,
            None,
            (bar.close - prior_low) / value,
            close_location,
            "balanced M15 with failed lower auction and causal reclaim",
        )
    return None


def _post_shock_signal(
    bars: Sequence[MarketBar],
    regime: RegimeSnapshot,
):
    if regime.regime != MarketRegime.POST_SHOCK or regime.direction == 0:
        return None

    bar = bars[-1]
    bar_range = bar.high - bar.low
    if bar_range <= 0 or regime.atr <= 0:
        return None
    close_location = (bar.close - bar.low) / bar_range
    aligned = (
        regime.direction > 0
        and bar.close > bar.open
        and close_location >= 0.60
    ) or (
        regime.direction < 0
        and bar.close < bar.open
        and close_location <= 0.40
    )
    if not aligned or bar_range > 0.90 * regime.atr:
        return None

    side = Side.BUY if regime.direction > 0 else Side.SELL
    raw_stop = bar.low if side == Side.BUY else bar.high
    return (
        side,
        raw_stop,
        1.8,
        12,
        0.65 * regime.atr,
        None,
        None,
        None,
        close_location,
        "post-shock M15 with aligned M5 continuation confirmation",
    )


def _no_signal_reason(
    regime: RegimeSnapshot,
    mechanism: OpportunityMechanism,
) -> str:
    return (
        f"{mechanism.value} conditions are not complete in "
        f"{regime.regime.value} regime"
    )


def _causal_percentile(values: Sequence[float], index: int) -> float:
    start = max(0, index - VOLATILITY_PERCENTILE_LOOKBACK)
    history = list(values[start:index])
    if not history:
        return 0.5
    current = values[index]
    return sum(value <= current for value in history) / len(history)


def _momentum_12_atr(
    bars_m15: Sequence[MarketBar],
    regime: RegimeSnapshot,
    index: int,
) -> float | None:
    if index < 12 or regime.atr <= 0:
        return None
    return (bars_m15[index].close - bars_m15[index - 12].close) / regime.atr


def _sizing_snapshot(
    spec: BrokerSymbolSpec,
    entry: float,
    stop: float,
    risk_fraction: float,
) -> ShadowSizingSnapshot:
    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=entry,
            stop=stop,
            requested_risk_fraction=risk_fraction,
        )
    )
    return ShadowSizingSnapshot(
        risk_fraction=risk_fraction,
        approved=sizing.approved,
        reason=sizing.reason,
        lots=sizing.lots,
        expected_loss_eur=sizing.expected_loss_eur,
        spread_to_stop=sizing.spread_to_stop,
    )
