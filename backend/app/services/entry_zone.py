from collections.abc import Sequence
from datetime import datetime, timedelta

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest
from app.domain.entry_zone import EntryZoneSizing, EntryZoneState, ExecutableEntryZoneV2
from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateV2
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import OpportunityState, OpportunityStateSnapshot
from app.domain.runtime_capital import RuntimeCapitalSnapshot
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.opportunity_strategies import _atr_series
from app.services.opportunity_triggers import (
    inspect_break_retest_trigger,
    inspect_directional_pullback_trigger,
)
from app.services.replay import RegimeReplay


def _closed_at(bar: MarketBar) -> datetime:
    return bar.timestamp + timedelta(minutes=5 if bar.timeframe is Timeframe.M5 else 15)


def _trigger_for(
    bars_m5: Sequence[MarketBar], bars_m15: Sequence[MarketBar], snapshot: OpportunityStateSnapshot
):
    if snapshot.triggered_at is None:
        return None, None, None, []
    m5 = [bar for bar in bars_m5 if _closed_at(bar) <= snapshot.triggered_at]
    m15 = [bar for bar in bars_m15 if _closed_at(bar) <= snapshot.triggered_at]
    if not m5 or not m15:
        return None, None, None, m5
    regimes = RegimeReplay(max_history=max(250, len(m15))).replay(m15)
    regime = regimes[-1]
    atr = _atr_series(m5)
    inspection = (
        inspect_break_retest_trigger(m5, atr, regime)
        if snapshot.mechanism is OpportunityMechanism.BREAK_RETEST_REACCEL
        else inspect_directional_pullback_trigger(m5, atr, regime)
    )
    return inspection, regime, atr[-1] if atr else None, m5


def _stop_for(inspection, entry: float, spread: float, atr_m5: float, mechanism: OpportunityMechanism) -> float:
    if mechanism is OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
        return inspection.raw_stop if inspection.side is Side.BUY else inspection.raw_stop + spread
    if inspection.side is Side.BUY:
        return min(inspection.raw_stop, entry - inspection.stop_atr)
    return max(inspection.raw_stop + spread, entry + inspection.stop_atr)


def _landmark(snapshot: MarketStateV2, side: Side, entry: float, stop_distance: float):
    context = snapshot.session_context
    if context is None:
        return (None,) * 5
    levels = (
        ("previous_day_high", context.previous_day_high),
        ("previous_day_low", context.previous_day_low),
        ("asia_high", context.asia_high),
        ("asia_low", context.asia_low),
        ("london_high_so_far", context.london_high_so_far),
        ("london_low_so_far", context.london_low_so_far),
        ("us_high_so_far", context.us_high_so_far),
        ("us_low_so_far", context.us_low_so_far),
    )
    candidates = [item for item in levels if item[1] is not None and ((side is Side.BUY and item[1] > entry) or (side is Side.SELL and item[1] < entry))]
    if not candidates:
        return (None,) * 5
    name, price = min(candidates, key=lambda item: abs(item[1] - entry))
    distance = abs(price - entry)
    atr = snapshot.atr_m5
    return name, price, distance, distance / atr if atr and atr > 0 else None, distance / stop_distance if stop_distance > 0 else None


def build_entry_zone(
    *,
    snapshot: OpportunityStateSnapshot,
    market_state: MarketStateV2,
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    quote,
    spec: BrokerSymbolSpec | None,
    capital: RuntimeCapitalSnapshot,
) -> ExecutableEntryZoneV2:
    base = {
        "symbol": snapshot.symbol, "mechanism": snapshot.mechanism.value, "side": snapshot.side,
        "opportunity_state": snapshot.state, "evaluated_at": market_state.evaluated_at,
        "extension_atr": market_state.extension_atr, "momentum_atr": market_state.momentum_atr,
        "acceleration_atr": market_state.acceleration_atr, "efficiency_m5": market_state.efficiency_m5,
        "range_expansion_ratio": market_state.range_expansion_ratio, "exhaustion_proxy": market_state.exhaustion_proxy,
        "macro_available": market_state.macro.available, "macro_blocked": market_state.macro.blocked,
    }
    if snapshot.state is not OpportunityState.TRIGGERED:
        return ExecutableEntryZoneV2(**base, state=EntryZoneState.NOT_APPLICABLE, reason="entry zone applies only after a causal trigger")
    if quote is None or quote.as_of > market_state.evaluated_at or quote.status.value != "live":
        return ExecutableEntryZoneV2(**base, state=EntryZoneState.DATA_UNAVAILABLE, trigger_at=snapshot.triggered_at, trigger_source_closed_at=snapshot.triggered_at, reason="fresh causal execution quote unavailable")
    if spec is None or capital.capital_eur is None:
        return ExecutableEntryZoneV2(**base, state=EntryZoneState.DATA_UNAVAILABLE, trigger_at=snapshot.triggered_at, reason="broker specification or DEMO capital unavailable")
    inspection, _, atr_m5, trigger_bars = _trigger_for(bars_m5, bars_m15, snapshot)
    if inspection is None or atr_m5 is None or market_state.atr_m5 is None:
        return ExecutableEntryZoneV2(**base, state=EntryZoneState.DATA_UNAVAILABLE, trigger_at=snapshot.triggered_at, reason="trigger geometry unavailable")
    entry = quote.ask if inspection.side is Side.BUY else quote.bid
    spread = quote.ask - quote.bid
    stop = _stop_for(inspection, entry, spread, atr_m5, snapshot.mechanism)
    distance = abs(entry - stop)
    sizing_result = size_position(PositionSizeRequest(spec=spec.model_copy(update={"bid": quote.bid, "ask": quote.ask}), entry=entry, stop=stop, capital_eur=capital.capital_eur))
    loss_per_price = spec.tick_value / spec.tick_size * spec.min_lot
    maximum_distance = sizing_result.risk_budget_eur / loss_per_price if loss_per_price > 0 else None
    sizing = EntryZoneSizing(capital_source=capital.source.value, risk_budget_eur=sizing_result.risk_budget_eur, lots=sizing_result.lots, expected_loss_eur=sizing_result.expected_loss_eur, min_lot_loss_eur=sizing_result.min_lot_loss_eur, estimated_margin_eur=sizing_result.estimated_margin_eur, sizing_reason=sizing_result.reason)
    chase = None
    if trigger_bars and market_state.atr_m5 and market_state.atr_m5 > 0:
        trigger_price = trigger_bars[-1].close
        favorable = entry - trigger_price if inspection.side is Side.BUY else trigger_price - entry
        chase = favorable / market_state.atr_m5
    landmark_type, landmark_price, landmark_distance, landmark_atr, room = _landmark(market_state, inspection.side, entry, distance)
    state = EntryZoneState.CURRENTLY_EXECUTABLE if sizing_result.approved else EntryZoneState.ECONOMICALLY_BLOCKED
    return ExecutableEntryZoneV2(**base, state=state, side=inspection.side, trigger_at=snapshot.triggered_at, trigger_source_closed_at=snapshot.triggered_at, current_entry=entry, structural_stop=stop, current_stop_distance=distance, minimum_stop_distance_for_spread=spread / settings.max_spread_to_stop, maximum_stop_distance_for_min_lot_budget=maximum_distance, spread=spread, spread_to_stop=sizing_result.spread_to_stop, sizing=sizing, post_trigger_chase_atr=chase, favorable_landmark_type=landmark_type, favorable_landmark_price=landmark_price, favorable_landmark_distance=landmark_distance, favorable_landmark_distance_atr_m5=landmark_atr, room_to_landmark_r=room, reason=sizing_result.reason)
