from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_state import OpportunityState, OpportunityStateSnapshot
from app.domain.trading import Side
from app.domain.trigger_engine import TriggerEngineState, TriggerEngineV2Snapshot
from app.domain.xau_microbar import XauMicrobarM1
from app.services.opportunity_strategies import _atr_series
from app.services.xau_microbar import _geometry_window

SUPPORTED = {
    OpportunityMechanism.BREAK_RETEST_REACCEL,
    OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
}


def _closed_at(row: XauMicrobarM1) -> datetime:
    return row.minute_at + timedelta(minutes=1)


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


def _side_imbalance(row: XauMicrobarM1, side: Side | None) -> float | None:
    if row.mid_tick_imbalance is None or side is None:
        return None
    return row.mid_tick_imbalance if side is Side.BUY else -row.mid_tick_imbalance


def _latest_atr(bars: Sequence[MarketBar], at: datetime) -> float | None:
    causal = [bar for bar in bars if bar.timestamp + timedelta(minutes=5) <= at]
    values = _atr_series(causal)
    return values[-1] if values else None


def _reference(bars: Sequence[MarketBar], mechanism: OpportunityMechanism, side: Side, armed_at: datetime) -> float | None:
    causal = [bar for bar in bars if bar.timestamp + timedelta(minutes=5) <= armed_at]
    if mechanism is OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
        return (causal[-1].high if side is Side.BUY else causal[-1].low) if causal else None
    if len(causal) < 15:
        return None
    base = causal[-15:-3]
    if not base:
        return None
    return max(bar.high for bar in base) if side is Side.BUY else min(bar.low for bar in base)


def _close_location(row: XauMicrobarM1) -> float:
    span = row.mid_high - row.mid_low
    return (row.mid_close - row.mid_low) / span if span > 0 else 0.5


def _is_valid(row: XauMicrobarM1, side: Side, mechanism: OpportunityMechanism, reference: float) -> bool:
    location = _close_location(row)
    if mechanism is OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
        return (row.mid_close > row.mid_open and row.mid_close > reference) if side is Side.BUY else (row.mid_close < row.mid_open and row.mid_close < reference)
    if side is Side.BUY:
        return row.mid_close > reference and row.mid_close > row.mid_open and location >= 0.60
    return row.mid_close < reference and row.mid_close < row.mid_open and location <= 0.40


def _decorate_m1(result: dict, row: XauMicrobarM1, side: Side | None, rows: Sequence[XauMicrobarM1]) -> None:
    result.update({
        "m1_available": True,
        "latest_closed_m1_at": row.minute_at,
        "latest_closed_m1_closed_at": _closed_at(row),
        "directional_tick_samples": row.directional_tick_samples,
        "raw_tick_imbalance": row.mid_tick_imbalance,
        "side_aligned_tick_imbalance": _side_imbalance(row, side),
        "m1_signed_move": row.mid_close - row.mid_open,
        "m1_close_location": _close_location(row),
        "m1_average_spread": row.average_spread,
        "geometry_5m": _geometry_window(list(rows), 5),
        "geometry_15m": _geometry_window(list(rows), 15),
    })


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

    upper = triggered.source_closed_at if triggered else evaluated_at
    rows = sorted(
        [row for row in microbars if _closed_at(row) > armed.source_closed_at and _closed_at(row) <= upper],
        key=lambda row: row.minute_at,
    )
    if not rows:
        state = TriggerEngineState.V1_TRIGGERED if triggered else TriggerEngineState.M1_UNAVAILABLE
        return TriggerEngineV2Snapshot(**_base(snapshot, evaluated_at, state, "V1 trigger is the reference" if triggered else "no closed M1 data after ARMED"), m1_status="unavailable")

    latest = rows[-1]
    expected_closed_at = evaluated_at.replace(second=0, microsecond=0)
    status = "historical" if triggered else ("fresh" if _closed_at(latest) == expected_closed_at else "stale")
    result = _base(snapshot, evaluated_at, TriggerEngineState.WAITING, "no causal M1 re-acceleration yet")
    _decorate_m1(result, latest, snapshot.side, rows)
    result["m1_status"] = status
    atr = atr_reference if atr_reference is not None else _latest_atr(bars_m5, armed.source_closed_at)
    if triggered and v1_reference_price is None:
        v1_bar = next((bar for bar in bars_m5 if bar.timestamp + timedelta(minutes=5) == triggered.source_closed_at), None)
        v1_reference_price = v1_bar.close if v1_bar else None
    result["v1_reference_price"] = v1_reference_price
    if status == "stale":
        result["reason"] = "closed M1 data is stale"
        return TriggerEngineV2Snapshot(**result)
    if snapshot.side is None:
        result["reason"] = "armed side unavailable"
        return TriggerEngineV2Snapshot(**result)
    reference = _reference(bars_m5, snapshot.mechanism, snapshot.side, armed.source_closed_at)
    if reference is None:
        result["reason"] = "causal trigger reference unavailable"
        result["state"] = TriggerEngineState.V1_TRIGGERED if triggered else TriggerEngineState.WAITING
        return TriggerEngineV2Snapshot(**result)

    early = next((candidate for candidate in rows if _is_valid(candidate, snapshot.side, snapshot.mechanism, reference)), None)
    if early is None:
        if triggered:
            result["state"] = TriggerEngineState.V1_TRIGGERED
            result["reason"] = "V1 trigger is the reference"
        return TriggerEngineV2Snapshot(**result)

    early_closed = _closed_at(early)
    early_price = early.ask_close if snapshot.side is Side.BUY else early.bid_close
    result.update({
        "state": TriggerEngineState.EARLY_TRIGGERED,
        "early_trigger_at": early_closed,
        "early_trigger_source_closed_at": early_closed,
        "early_trigger_price": early_price,
        "early_trigger_source": "M1_closed_reacceleration",
    })
    _decorate_m1(result, early, snapshot.side, [row for row in rows if _closed_at(row) <= early_closed])
    if triggered and triggered.source_closed_at >= early_closed:
        lead = (triggered.source_closed_at - early_closed).total_seconds()
        result["lead_seconds"] = lead
        result["lead_minutes"] = lead / 60
        if v1_reference_price is not None and atr and atr > 0:
            result["move_saved_vs_v1_atr"] = ((v1_reference_price - early_price) if snapshot.side is Side.BUY else (early_price - v1_reference_price)) / atr
    return TriggerEngineV2Snapshot(**result)
