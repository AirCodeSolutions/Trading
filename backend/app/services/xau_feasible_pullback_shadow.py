import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.domain.broker import PositionSizeRequest
from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.trading import Side
from app.domain.xau_feasible_pullback_shadow import (
    FeasiblePullbackStatus,
    XauFeasiblePullbackProbe,
    XauFeasiblePullbackState,
    XauFeasiblePullbackSummary,
)
from app.services.capital_risk import monetary_loss_per_lot, size_position
from app.services.mt4_market_data import load_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec

SYMBOL = "XAUUSD"
MECHANISM = OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL
STRATEGY_ID = f"{SYMBOL}:{MECHANISM.value}:risk_feasible_pullback"
STATE_FILE = "XAUUSD_asia_range_sweep_feasible_pullback_state.json"
LEDGER_FILE = "XAUUSD_asia_range_sweep_feasible_pullback.jsonl"
FILL_WINDOW_BARS = 3


def advance_xau_feasible_pullback_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    diagnostic: ShadowOpportunityDiagnostic,
    evaluated_at: datetime,
) -> XauFeasiblePullbackSummary:
    state_path = runtime_dir / STATE_FILE
    ledger_path = runtime_dir / LEDGER_FILE
    state = load_xau_feasible_pullback_state(state_path)
    if state is None:
        state = XauFeasiblePullbackState(started_at=evaluated_at)
        save_xau_feasible_pullback_state(state_path, state)
        return load_xau_feasible_pullback_summary(runtime_dir)

    spec = get_mt4_symbol_spec(files_dir, SYMBOL)
    if spec is None:
        return load_xau_feasible_pullback_summary(runtime_dir)
    bars = load_closed_market_bars(
        files_dir,
        SYMBOL,
        Timeframe.M5,
        evaluated_at=evaluated_at,
    )

    if state.open_probe is not None:
        resolved = resolve_xau_feasible_pullback_probe(
            state.open_probe,
            bars,
        )
        if resolved.status in {
            FeasiblePullbackStatus.NO_FILL,
            FeasiblePullbackStatus.STOP,
            FeasiblePullbackStatus.TARGET,
            FeasiblePullbackStatus.TIMEOUT,
        }:
            append_xau_feasible_pullback_probe(ledger_path, resolved)
            state.open_probe = None
        else:
            state.open_probe = resolved

    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    if (
        state.open_probe is None
        and _eligible_blocked_signal(diagnostic)
        and signal_at >= state.started_at
        and (
            state.last_started_signal_at is None
            or signal_at > state.last_started_signal_at
        )
    ):
        probe = create_xau_feasible_pullback_probe(
            diagnostic,
            spec,
            signal_at=signal_at,
        )
        if probe is not None:
            state.open_probe = probe
            state.last_started_signal_at = signal_at

    save_xau_feasible_pullback_state(state_path, state)
    return load_xau_feasible_pullback_summary(runtime_dir)


def _eligible_blocked_signal(
    diagnostic: ShadowOpportunityDiagnostic,
) -> bool:
    return bool(
        diagnostic.symbol.upper() == SYMBOL
        and diagnostic.mechanism == MECHANISM
        and diagnostic.state == ShadowSignalState.SIGNAL_BLOCKED
        and diagnostic.side is not None
        and diagnostic.structural_stop is not None
        and diagnostic.target_r is not None
        and diagnostic.max_holding_bars is not None
        and diagnostic.base_risk is not None
        and not diagnostic.base_risk.approved
        and diagnostic.base_risk.reason
        == "minimum broker lot exceeds the risk budget"
    )


def create_xau_feasible_pullback_probe(
    diagnostic: ShadowOpportunityDiagnostic,
    spec,
    *,
    signal_at: datetime,
) -> XauFeasiblePullbackProbe | None:
    if not _eligible_blocked_signal(diagnostic):
        return None
    assert diagnostic.side is not None
    assert diagnostic.structural_stop is not None
    assert diagnostic.target_r is not None
    assert diagnostic.max_holding_bars is not None

    risk_budget = settings.reference_capital_eur * settings.risk_per_trade_fraction
    loss_per_price_at_min_lot = (
        monetary_loss_per_lot(spec, 1.0) * spec.min_lot
    )
    if loss_per_price_at_min_lot <= 0:
        return None
    max_stop_distance = risk_budget / loss_per_price_at_min_lot
    stop = diagnostic.structural_stop

    if diagnostic.side == Side.BUY:
        limit_entry = stop + max_stop_distance
        if limit_entry >= spec.ask:
            return None
    else:
        limit_entry = stop - max_stop_distance
        if limit_entry <= spec.bid:
            return None

    sizing = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=limit_entry,
            stop=stop,
            requested_risk_fraction=settings.risk_per_trade_fraction,
        )
    )
    if not sizing.approved:
        return None

    risk_distance = abs(limit_entry - stop)
    target = (
        limit_entry + diagnostic.target_r * risk_distance
        if diagnostic.side == Side.BUY
        else limit_entry - diagnostic.target_r * risk_distance
    )
    return XauFeasiblePullbackProbe(
        probe_id=f"{STRATEGY_ID}:{signal_at.isoformat()}",
        signal_at=signal_at,
        side=diagnostic.side,
        stop_price=stop,
        limit_entry=limit_entry,
        target_price=target,
        spread_at_entry=spec.spread,
        target_r=diagnostic.target_r,
        max_holding_bars=diagnostic.max_holding_bars,
        fill_window_bars=FILL_WINDOW_BARS,
        risk_eur=sizing.expected_loss_eur,
    )


def resolve_xau_feasible_pullback_probe(
    probe: XauFeasiblePullbackProbe,
    bars,
) -> XauFeasiblePullbackProbe:
    if probe.status not in {
        FeasiblePullbackStatus.PENDING,
        FeasiblePullbackStatus.FILLED,
    }:
        return probe

    horizon_end = probe.signal_at + timedelta(
        minutes=5 * probe.max_holding_bars
    )
    future = [
        bar
        for bar in bars
        if probe.signal_at <= bar.timestamp < horizon_end
    ]
    if not future:
        return probe

    current = probe
    if current.status == FeasiblePullbackStatus.PENDING:
        fill_candidates = future[: current.fill_window_bars]
        fill_bar = None
        for bar in fill_candidates:
            if current.side == Side.BUY:
                ask_low = bar.low + current.spread_at_entry
                if ask_low <= current.limit_entry:
                    fill_bar = bar
                    break
            elif bar.high >= current.limit_entry:
                fill_bar = bar
                break

        if fill_bar is None:
            if len(fill_candidates) >= current.fill_window_bars:
                return current.model_copy(
                    update={
                        "status": FeasiblePullbackStatus.NO_FILL,
                        "exit_at": fill_candidates[-1].timestamp,
                    }
                )
            return current

        current = current.model_copy(
            update={
                "status": FeasiblePullbackStatus.FILLED,
                "fill_at": fill_bar.timestamp,
            }
        )

    assert current.fill_at is not None
    trade_bars = [bar for bar in future if bar.timestamp >= current.fill_at]
    for index, bar in enumerate(trade_bars, start=1):
        if current.side == Side.BUY:
            stop_hit = bar.low <= current.stop_price
            target_hit = bar.high >= current.target_price
        else:
            ask_high = bar.high + current.spread_at_entry
            ask_low = bar.low + current.spread_at_entry
            stop_hit = ask_high >= current.stop_price
            target_hit = ask_low <= current.target_price

        if stop_hit:
            return _close_probe(
                current,
                status=FeasiblePullbackStatus.STOP,
                exit_at=bar.timestamp,
                exit_price=current.stop_price,
                result_r=-1.0,
                bars_held=index,
            )
        if target_hit:
            return _close_probe(
                current,
                status=FeasiblePullbackStatus.TARGET,
                exit_at=bar.timestamp,
                exit_price=current.target_price,
                result_r=current.target_r,
                bars_held=index,
            )

    last_expected_bar = horizon_end - timedelta(minutes=5)
    if future[-1].timestamp < last_expected_bar:
        return current.model_copy(update={"bars_held": len(trade_bars)})

    last = future[-1]
    risk_distance = abs(current.limit_entry - current.stop_price)
    if current.side == Side.BUY:
        exit_price = last.close
        result_r = (exit_price - current.limit_entry) / risk_distance
    else:
        exit_price = last.close + current.spread_at_entry
        result_r = (current.limit_entry - exit_price) / risk_distance
    return _close_probe(
        current,
        status=FeasiblePullbackStatus.TIMEOUT,
        exit_at=last.timestamp,
        exit_price=exit_price,
        result_r=result_r,
        bars_held=len(trade_bars),
    )


def _close_probe(
    probe: XauFeasiblePullbackProbe,
    *,
    status: FeasiblePullbackStatus,
    exit_at: datetime,
    exit_price: float,
    result_r: float,
    bars_held: int,
) -> XauFeasiblePullbackProbe:
    return probe.model_copy(
        update={
            "status": status,
            "exit_at": exit_at,
            "exit_price": exit_price,
            "result_r": result_r,
            "bars_held": bars_held,
        }
    )


def load_xau_feasible_pullback_state(
    path: Path,
) -> XauFeasiblePullbackState | None:
    if not path.is_file():
        return None
    try:
        return XauFeasiblePullbackState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def save_xau_feasible_pullback_state(
    path: Path,
    state: XauFeasiblePullbackState,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def append_xau_feasible_pullback_probe(
    path: Path,
    probe: XauFeasiblePullbackProbe,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(probe.model_dump_json())
        handle.write("\n")


def load_xau_feasible_pullback_probes(
    path: Path,
) -> list[XauFeasiblePullbackProbe]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    XauFeasiblePullbackProbe.model_validate(
                        json.loads(line)
                    )
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def load_xau_feasible_pullback_summary(
    runtime_dir: Path,
) -> XauFeasiblePullbackSummary:
    state = load_xau_feasible_pullback_state(runtime_dir / STATE_FILE)
    rows = load_xau_feasible_pullback_probes(runtime_dir / LEDGER_FILE)
    filled = [row for row in rows if row.result_r is not None]
    results = [row.result_r for row in filled if row.result_r is not None]
    return XauFeasiblePullbackSummary(
        strategy_id=STRATEGY_ID,
        started_at=state.started_at if state is not None else None,
        resolved=len(rows),
        filled=len(filled),
        no_fill=sum(
            row.status == FeasiblePullbackStatus.NO_FILL for row in rows
        ),
        wins=sum(value > 0 for value in results),
        losses=sum(value <= 0 for value in results),
        total_r=sum(results),
        expectancy_r=(sum(results) / len(results) if results else 0.0),
        open_probe=state.open_probe if state is not None else None,
        recent=rows[-10:][::-1],
    )
