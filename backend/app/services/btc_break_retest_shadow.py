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

VOLATILITY_PERCENTILE_LOOKBACK = 500
MAX_SNAPSHOT_AGE = timedelta(minutes=10)


def scan_btc_break_retest_shadow(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    spec: BrokerSymbolSpec,
    evaluated_at: datetime,
    *,
    capital_eur: float | None = None,
) -> ShadowOpportunityDiagnostic:
    if spec.symbol.upper() != "BTCUSD":
        raise ValueError("BTC break/retest shadow scanner requires BTCUSD spec")
    if len(bars_m5) < 30 or len(bars_m15) < 50:
        raise ValueError("insufficient M5/M15 closed bars for shadow scan")
    if evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    snapshots = RegimeReplay(max_history=600).replay(bars_m15)
    m15_close_times = [bar.timestamp + timedelta(minutes=15) for bar in bars_m15]
    latest_m5 = bars_m5[-1]
    signal_close = latest_m5.timestamp + timedelta(minutes=5)
    regime_index = bisect_right(m15_close_times, signal_close) - 1
    if regime_index < 0:
        raise ValueError("no causal M15 regime available for latest M5 close")
    regime = snapshots[regime_index]

    volatility_percentile = _causal_percentile(
        [item.atr_ratio for item in snapshots],
        regime_index,
    )
    momentum_12_atr = _momentum_12_atr(bars_m15, regime, regime_index)

    base_payload = {
        "symbol": "BTCUSD",
        "mechanism": OpportunityMechanism.BREAK_RETEST_REACCEL,
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

    snapshot_age = evaluated_at - signal_close
    if snapshot_age > MAX_SNAPSHOT_AGE or snapshot_age < -timedelta(minutes=1):
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason="latest M5 snapshot is stale or timestamp-inconsistent",
        )

    if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason="latest causal M15 regime is not directional expansion",
        )

    atr_m5 = _atr_series(bars_m5)
    signal = _latest_break_retest_signal(bars_m5, atr_m5, regime)
    if signal is None:
        return ShadowOpportunityDiagnostic(
            **base_payload,
            state=ShadowSignalState.NO_SIGNAL,
            reason="latest closed M5 bar does not complete break/retest/re-acceleration",
        )

    side, raw_stop, break_strength, retest_depth, reclaim, close_location = signal
    entry = spec.ask if side == Side.BUY else spec.bid
    current_atr_m5 = atr_m5[-1]
    if side == Side.BUY:
        structural_stop = min(raw_stop, entry - 0.65 * current_atr_m5)
    else:
        structural_stop = max(
            raw_stop + spec.spread,
            entry + 0.65 * current_atr_m5,
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
    reason = (
        "latest closed M5 bar completes causal BTC break/retest signal"
        if base_sizing.approved
        else f"signal exists but base-risk execution is blocked: {base_sizing.reason}"
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
        base_risk=base_sizing,
        max_risk=max_sizing,
        reason=reason,
    )


def _latest_break_retest_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    regime: RegimeSnapshot,
) -> tuple[Side, float, float, float, float, float] | None:
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
        break_strength = (max(item.close for item in recent) - prior_high) / value
        retest_depth = (prior_high - bar.low) / value
        reclaim = (bar.close - prior_high) / value
        raw_stop = bar.low - 0.10 * value
        return (
            Side.BUY,
            raw_stop,
            break_strength,
            retest_depth,
            reclaim,
            close_location,
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
    break_strength = (prior_low - min(item.close for item in recent)) / value
    retest_depth = (bar.high - prior_low) / value
    reclaim = (prior_low - bar.close) / value
    raw_stop = bar.high + 0.10 * value
    return (
        Side.SELL,
        raw_stop,
        break_strength,
        retest_depth,
        reclaim,
        close_location,
    )


def _causal_percentile(
    values: Sequence[float],
    index: int,
) -> float:
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
    effective_capital = (
        settings.reference_capital_eur
        if capital_eur is None
        else capital_eur
    )
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
