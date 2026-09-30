from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest
from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.shadow import (
    PostShockResearchContext,
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
    StopGeometrySource,
)
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.opportunity_strategies import (
    _asia_range_sweep_signal,
    _atr_series,
    _structural_displacement_sequence_signal,
    _structural_persistence_sequence_signal,
)
from app.services.opportunity_triggers import (
    inspect_break_retest_trigger,
    inspect_directional_pullback_trigger,
)
from app.services.regime import shock_bar_metrics
from app.services.replay import RegimeReplay
from app.services.session_continuity import reopen_warmup_remaining
from app.services.session_landmarks import build_session_landmark_context

VOLATILITY_PERCENTILE_LOOKBACK = 500
MAX_SNAPSHOT_AGE = timedelta(minutes=10)


def scan_shadow_opportunity(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    spec: BrokerSymbolSpec,
    mechanism: OpportunityMechanism,
    evaluated_at: datetime,
    *,
    capital_eur: float | None = None,
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
            reason=(f"session reopen warmup: {warmup_remaining} closed M5 bar(s) remaining"),
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
    if mechanism in {
        OpportunityMechanism.DIRECTIONAL_TRANSITION,
        OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
    }:
        if side == Side.BUY:
            structural_stop = entry - stop_atr
            stop_source = StopGeometrySource.ATR_DISTANCE
        else:
            structural_stop = entry + stop_atr + spec.spread
            stop_source = StopGeometrySource.ATR_DISTANCE_WITH_SPREAD
    elif mechanism in {
        OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
    }:
        if side == Side.BUY:
            structural_stop = raw_stop
            stop_source = StopGeometrySource.RAW_STRUCTURE
        else:
            structural_stop = raw_stop + spec.spread
            stop_source = StopGeometrySource.RAW_STRUCTURE_WITH_SPREAD
    elif side == Side.BUY:
        structural_stop = min(raw_stop, entry - stop_atr)
        stop_source = (
            StopGeometrySource.RAW_STRUCTURE_FLOOR_COMPARISON
            if raw_stop <= entry - stop_atr
            else StopGeometrySource.ATR_DISTANCE
        )
    else:
        structural_stop = max(raw_stop + spec.spread, entry + stop_atr)
        stop_source = (
            StopGeometrySource.RAW_STRUCTURE_FLOOR_COMPARISON_WITH_SPREAD
            if raw_stop + spec.spread >= entry + stop_atr
            else StopGeometrySource.ATR_DISTANCE
        )

    atr_m5_value = atr_m5[-1] if atr_m5 else None
    structural_stop_distance = abs(entry - structural_stop)
    structural_stop_atr_m5 = (
        structural_stop_distance / atr_m5_value if atr_m5_value and atr_m5_value > 0 else None
    )
    structural_stop_atr_m15 = structural_stop_distance / regime.atr if regime.atr > 0 else None
    spread_atr_m5 = spec.spread / atr_m5_value if atr_m5_value and atr_m5_value > 0 else None
    spread_atr_m15 = spec.spread / regime.atr if regime.atr > 0 else None
    session_landmark_context = build_session_landmark_context(
        bars_m5,
        signal_close,
        entry,
        side,
        atr_m5=atr_m5_value,
        atr_m15=regime.atr,
    )
    post_shock_research_context = (
        _post_shock_research_context(
            bars_m5,
            bars_m15,
            regime_index,
            regime,
            side,
            entry,
        )
        if mechanism == OpportunityMechanism.POST_SHOCK_CONTINUATION
        else None
    )

    base_sizing = _sizing_snapshot(
        spec,
        entry,
        structural_stop,
        settings.risk_per_trade_fraction,
        capital_eur=capital_eur,
    )
    max_sizing = _sizing_snapshot(
        spec,
        entry,
        structural_stop,
        settings.absolute_max_risk_fraction,
        capital_eur=capital_eur,
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
        raw_stop_price=raw_stop,
        stop_geometry_source=stop_source,
        stop_atr_distance=stop_atr,
        atr_m5=atr_m5_value,
        structural_stop_distance=structural_stop_distance,
        structural_stop_atr_m5=structural_stop_atr_m5,
        structural_stop_atr_m15=structural_stop_atr_m15,
        spread_at_signal=spec.spread,
        spread_atr_m5=spread_atr_m5,
        spread_atr_m15=spread_atr_m15,
        broker_digits=spec.digits,
        broker_tick_size=spec.tick_size,
        session_landmark_context=session_landmark_context,
        target_r=target_r,
        max_holding_bars=max_holding_bars,
        base_risk=base_sizing,
        max_risk=max_sizing,
        post_shock_research_context=post_shock_research_context,
        reason=final_reason,
    )


def _post_shock_research_context(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    shock_index: int,
    regime: RegimeSnapshot,
    side: Side,
    signal_reference_price: float,
) -> PostShockResearchContext | None:
    metrics = shock_bar_metrics(bars_m15, shock_index)
    if metrics is None:
        return None
    shock_true_range, previous_atr, shock_ratio, body_fraction, close_location, direction = metrics
    shock_bar = bars_m15[shock_index]
    pre_shock_close = bars_m15[shock_index - 1].close
    shock_known_at = shock_bar.timestamp + timedelta(minutes=15)
    signal_known_at = bars_m5[-1].timestamp + timedelta(minutes=5)
    latency = (signal_known_at - shock_known_at).total_seconds() / 60
    if latency < 0:
        return None

    causal_m5 = [
        bar
        for bar in bars_m5
        if bar.timestamp >= shock_bar.timestamp
        and bar.timestamp + timedelta(minutes=5) <= signal_known_at
    ]
    if side == Side.BUY:
        consumed = signal_reference_price - pre_shock_close
        mfe = max((bar.high - pre_shock_close for bar in causal_m5), default=None)
        mae = max((pre_shock_close - bar.low for bar in causal_m5), default=None)
    else:
        consumed = pre_shock_close - signal_reference_price
        mfe = max((pre_shock_close - bar.low for bar in causal_m5), default=None)
        mae = max((bar.high - pre_shock_close for bar in causal_m5), default=None)

    def normalized(value: float | None) -> float | None:
        return value / previous_atr if value is not None and previous_atr > 0 else None

    return PostShockResearchContext(
        shock_bar_at=shock_bar.timestamp,
        shock_known_at=shock_known_at,
        shock_open=shock_bar.open,
        shock_high=shock_bar.high,
        shock_low=shock_bar.low,
        shock_close=shock_bar.close,
        pre_shock_close=pre_shock_close,
        shock_true_range=shock_true_range,
        shock_previous_atr=previous_atr,
        shock_ratio=shock_ratio,
        shock_body_fraction=body_fraction,
        shock_close_location=close_location,
        shock_direction=direction,
        signal_known_at=signal_known_at,
        post_shock_latency_minutes=latency,
        post_shock_elapsed_complete_m5_bars=len(causal_m5),
        signal_reference_price=signal_reference_price,
        pre_signal_consumed_move=consumed,
        pre_signal_consumed_move_atr=normalized(consumed),
        pre_signal_mfe=mfe,
        pre_signal_mfe_atr=normalized(mfe),
        pre_signal_mae=mae,
        pre_signal_mae_atr=normalized(mae),
    )


def _detect_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
    previous_regime: RegimeSnapshot | None,
    is_new_m15_close: bool,
    mechanism: OpportunityMechanism,
) -> (
    tuple[
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
    ]
    | None
):
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
    if mechanism == OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
        return _directional_pullback_resumption_signal(
            bars,
            atr,
            regime,
        )
    if mechanism == OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL:
        return _asia_range_sweep_signal(bars, atr)
    if mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE:
        return _structural_displacement_sequence_signal(bars, atr)
    if mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE:
        return _structural_persistence_sequence_signal(bars, atr)
    return None


def _directional_pullback_resumption_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
):
    inspection = inspect_directional_pullback_trigger(bars, atr, regime)
    return inspection


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
    return inspect_break_retest_trigger(bars, atr, regime)


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
    aligned = (regime.direction > 0 and bar.close > bar.open and close_location >= 0.60) or (
        regime.direction < 0 and bar.close < bar.open and close_location <= 0.40
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
    return f"{mechanism.value} conditions are not complete in {regime.regime.value} regime"


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
    *,
    capital_eur: float | None = None,
) -> ShadowSizingSnapshot:
    effective_capital = settings.reference_capital_eur if capital_eur is None else capital_eur
    stop_distance = abs(entry - stop)
    spread_to_stop = spec.spread / stop_distance if stop_distance > 0 else 0.0
    if effective_capital <= 0:
        return ShadowSizingSnapshot(
            risk_fraction=risk_fraction,
            approved=False,
            reason="broker demo sizing capital is unavailable",
            lots=0.0,
            expected_loss_eur=0.0,
            spread_to_stop=spread_to_stop,
            capital_eur=0.0,
        )

    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=entry,
            stop=stop,
            requested_risk_fraction=risk_fraction,
            capital_eur=effective_capital,
        )
    )
    return ShadowSizingSnapshot(
        risk_fraction=risk_fraction,
        approved=sizing.approved,
        reason=sizing.reason,
        lots=sizing.lots,
        expected_loss_eur=sizing.expected_loss_eur,
        spread_to_stop=sizing.spread_to_stop,
        capital_eur=effective_capital,
    )
