from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import OpportunityState, OpportunityStateSnapshot
from app.domain.trading import Side
from app.domain.trigger_engine import TriggerEngineState, TriggerEngineV2Snapshot
from app.domain.xau_microbar import XauMicrobarM1

SUPPORTED = {
    OpportunityMechanism.BREAK_RETEST_REACCEL,
    OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
}


def _closed_rows(rows: Sequence[XauMicrobarM1], evaluated_at: datetime) -> list[XauMicrobarM1]:
    return [row for row in rows if row.minute_at + timedelta(minutes=1) <= evaluated_at]


def _base(snapshot: OpportunityStateSnapshot, evaluated_at: datetime, state: TriggerEngineState, reason: str) -> dict:
    armed = next((item for item in snapshot.provenance if item.state is OpportunityState.ARMED), None)
    triggered = next((item for item in snapshot.provenance if item.state is OpportunityState.TRIGGERED), None)
    return {
        "symbol": snapshot.symbol,
        "mechanism": snapshot.mechanism,
        "side": snapshot.side,
        "opportunity_state": snapshot.state,
        "state": state,
        "evaluated_at": evaluated_at,
        "armed_at": armed.at if armed else None,
        "armed_source_closed_at": armed.source_closed_at if armed else None,
        "v1_trigger_at": triggered.at if triggered else None,
        "v1_trigger_source_closed_at": triggered.source_closed_at if triggered else None,
        "reason": reason,
    }


def build_trigger_engine_snapshot(
    *,
    snapshot: OpportunityStateSnapshot,
    microbars: Sequence[XauMicrobarM1],
    evaluated_at: datetime,
    bars_m5: Sequence[MarketBar] = (),
    atr_reference: float | None = None,
    v1_reference_price: float | None = None,
) -> TriggerEngineV2Snapshot:
    if snapshot.mechanism not in SUPPORTED:
        return TriggerEngineV2Snapshot(**_base(snapshot, evaluated_at, TriggerEngineState.NOT_APPLICABLE, "mechanism not supported by Trigger Engine V2"))
    armed = next((item for item in snapshot.provenance if item.state is OpportunityState.ARMED), None)
    triggered = next((item for item in snapshot.provenance if item.state is OpportunityState.TRIGGERED), None)
    if snapshot.state in {OpportunityState.NONE, OpportunityState.SETUP, OpportunityState.INVALIDATED, OpportunityState.EXPIRED} or armed is None:
        return TriggerEngineV2Snapshot(**_base(snapshot, evaluated_at, TriggerEngineState.NOT_APPLICABLE, "causal ARMED transition is required"))
    upper = triggered.source_closed_at if triggered is not None else evaluated_at
    rows = [row for row in microbars if row.minute_at + timedelta(minutes=1) > armed.source_closed_at and row.minute_at + timedelta(minutes=1) <= upper and row.minute_at.tzinfo is not None and row.minute_at.tzinfo == evaluated_at.tzinfo]
    if not rows:
        state = TriggerEngineState.V1_TRIGGERED if triggered is not None else TriggerEngineState.M1_UNAVAILABLE
        return TriggerEngineV2Snapshot(**_base(snapshot, evaluated_at, state, "V1 trigger is the reference" if triggered else "no closed M1 data after ARMED"), m1_status="unavailable", v1_reference_price=v1_reference_price)
    latest = rows[-1]
    age = (evaluated_at - (latest.minute_at + timedelta(minutes=1))).total_seconds()
    status = "historical" if triggered is not None else ("fresh" if age <= 15 else "stale")
    common = _base(snapshot, evaluated_at, TriggerEngineState.WAITING, "no causal M1 re-acceleration yet")
    common.update({
        "m1_available": True,
        "m1_status": status,
        "latest_closed_m1_at": latest.minute_at,
        "latest_closed_m1_closed_at": latest.minute_at + timedelta(minutes=1),
        "directional_tick_samples": latest.directional_tick_samples,
        "raw_tick_imbalance": latest.mid_tick_imbalance,
        "side_aligned_tick_imbalance": (latest.mid_tick_imbalance if snapshot.side is Side.BUY else (-latest.mid_tick_imbalance if latest.mid_tick_imbalance is not None else None)),
        "m1_signed_move": latest.mid_close - latest.mid_open,
        "m1_close_location": ((latest.mid_close - latest.mid_low) / (latest.mid_high - latest.mid_low) if latest.mid_high > latest.mid_low else 0.5),
        "m1_average_spread": latest.average_spread,
    })
    if status == "stale":
        common["reason"] = "closed M1 data is stale"
        if triggered is not None:
            common["state"] = TriggerEngineState.V1_TRIGGERED
            common["reason"] = "V1 trigger is the reference"
        return TriggerEngineV2Snapshot(**common)
    if snapshot.side is None:
        return TriggerEngineV2Snapshot(**common, reason="armed side unavailable")
    reference = None
    if bars_m5:
        causal = [bar for bar in bars_m5 if bar.timestamp + timedelta(minutes=5) <= armed.source_closed_at]
        if len(causal) >= 2:
            second = causal[-1]
            if snapshot.mechanism is OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
                reference = second.high if snapshot.side is Side.BUY else second.low
            elif len(causal) >= 15:
                base = causal[-15:-3]
                reference = max(bar.high for bar in base) if snapshot.side is Side.BUY else min(bar.low for bar in base)
    if reference is None:
        return TriggerEngineV2Snapshot(**common, state=TriggerEngineState.V1_TRIGGERED if triggered else TriggerEngineState.WAITING, reason="V1 trigger is the reference" if triggered else "causal trigger reference unavailable")
    valid = (
        latest.mid_close > latest.mid_open and latest.mid_close > reference
        if snapshot.side is Side.BUY
        else latest.mid_close < latest.mid_open and latest.mid_close < reference
    )
    if not valid:
        if triggered is not None:
            common["state"] = TriggerEngineState.V1_TRIGGERED
            common["reason"] = "V1 trigger is the reference"
        return TriggerEngineV2Snapshot(**common)
    price = latest.ask_close if snapshot.side is Side.BUY else latest.bid_close
    common.update({"state": TriggerEngineState.EARLY_TRIGGERED, "early_trigger_at": latest.minute_at + timedelta(minutes=1), "early_trigger_source_closed_at": latest.minute_at + timedelta(minutes=1), "early_trigger_price": price, "early_trigger_source": "M1_closed_reacceleration"})
    if triggered is not None:
        common["v1_trigger_at"] = triggered.at
        common["v1_trigger_source_closed_at"] = triggered.source_closed_at
        if triggered.source_closed_at >= latest.minute_at + timedelta(minutes=1):
            lead = (triggered.source_closed_at - (latest.minute_at + timedelta(minutes=1))).total_seconds()
            common["lead_seconds"] = lead
            common["lead_minutes"] = lead / 60
            if v1_reference_price is not None and atr_reference and atr_reference > 0:
                common["move_saved_vs_v1_atr"] = ((v1_reference_price - price) if snapshot.side is Side.BUY else (price - v1_reference_price)) / atr_reference
    return TriggerEngineV2Snapshot(**common)
