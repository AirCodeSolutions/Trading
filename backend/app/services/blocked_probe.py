from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.blocked_probe import (
    BlockedOpportunityProbe,
    BlockedProbeState,
    BlockedProbeSummary,
)
from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import PaperTradeStatus
from app.domain.trading import Side

DEFAULT_TARGET_R = 1.8
DEFAULT_MAX_HOLDING_BARS = 18
RECENT_PROBES_LIMIT = 10


def advance_blocked_probe_book(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    bars_m5: Sequence[MarketBar],
    state_path: Path,
    probes_path: Path,
    evaluated_at: datetime,
) -> BlockedProbeSummary:
    state = load_blocked_probe_state(state_path)

    if state.open_probe is not None:
        resolved = resolve_open_probe(state.open_probe, bars_m5)
        if resolved.status != PaperTradeStatus.OPEN:
            append_closed_probe(probes_path, resolved)
            state.open_probe = None
        else:
            state.open_probe = resolved

    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    if (
        state.open_probe is None
        and diagnostic.state == ShadowSignalState.SIGNAL_BLOCKED
        and diagnostic.side is not None
        and diagnostic.structural_stop is not None
        and diagnostic.base_risk is not None
        and not diagnostic.base_risk.approved
        and (
            state.last_started_signal_at is None
            or signal_at > state.last_started_signal_at
        )
    ):
        state.open_probe = create_blocked_probe(
            diagnostic=diagnostic,
            spec=spec,
            evaluated_at=evaluated_at,
        )
        state.last_started_signal_at = signal_at

    save_blocked_probe_state(state_path, state)
    return load_blocked_probe_summary(state_path, probes_path)


def create_blocked_probe(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    evaluated_at: datetime,
) -> BlockedOpportunityProbe:
    if diagnostic.side is None:
        raise ValueError("blocked probe requires a side")
    if diagnostic.structural_stop is None:
        raise ValueError("blocked probe requires a structural stop")
    if diagnostic.base_risk is None or diagnostic.base_risk.approved:
        raise ValueError("blocked probe requires blocked base-risk sizing")

    side = diagnostic.side
    entry = spec.ask if side == Side.BUY else spec.bid
    stop = diagnostic.structural_stop
    risk_distance = entry - stop if side == Side.BUY else stop - entry
    if risk_distance <= 0:
        raise ValueError("blocked probe stop geometry is invalid")

    target_r = diagnostic.target_r or DEFAULT_TARGET_R
    max_holding_bars = (
        diagnostic.max_holding_bars or DEFAULT_MAX_HOLDING_BARS
    )
    target = (
        entry + target_r * risk_distance
        if side == Side.BUY
        else entry - target_r * risk_distance
    )
    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)

    return BlockedOpportunityProbe(
        probe_id=(
            f"{diagnostic.symbol}-{diagnostic.mechanism.value}-"
            f"blocked-{signal_at.isoformat()}"
        ),
        symbol=diagnostic.symbol,
        mechanism=diagnostic.mechanism,
        side=side,
        signal_at=signal_at,
        opened_at=evaluated_at,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        spread_at_entry=spec.spread,
        risk_distance=risk_distance,
        target_r=target_r,
        max_holding_bars=max_holding_bars,
        block_reason=diagnostic.base_risk.reason,
        max_risk_approved=bool(
            diagnostic.max_risk is not None
            and diagnostic.max_risk.approved
        ),
        max_risk_reason=(
            diagnostic.max_risk.reason
            if diagnostic.max_risk is not None
            else None
        ),
    )


def resolve_open_probe(
    probe: BlockedOpportunityProbe,
    bars_m5: Sequence[MarketBar],
) -> BlockedOpportunityProbe:
    if probe.status != PaperTradeStatus.OPEN:
        return probe

    first_full_bar_at = _next_full_m5_bar_start(probe.opened_at)
    future_bars = [
        bar for bar in bars_m5 if bar.timestamp >= first_full_bar_at
    ][: probe.max_holding_bars]

    for index, bar in enumerate(future_bars, start=1):
        if probe.side == Side.BUY:
            stop_hit = bar.low <= probe.stop_price
            target_hit = bar.high >= probe.target_price
        else:
            ask_high = bar.high + probe.spread_at_entry
            ask_low = bar.low + probe.spread_at_entry
            stop_hit = ask_high >= probe.stop_price
            target_hit = ask_low <= probe.target_price

        if stop_hit:
            return _close_probe(
                probe,
                status=PaperTradeStatus.STOP,
                exit_at=bar.timestamp,
                exit_price=probe.stop_price,
                result_r=-1.0,
                bars_held=index,
            )
        if target_hit:
            return _close_probe(
                probe,
                status=PaperTradeStatus.TARGET,
                exit_at=bar.timestamp,
                exit_price=probe.target_price,
                result_r=probe.target_r,
                bars_held=index,
            )

    if len(future_bars) < probe.max_holding_bars:
        return probe.model_copy(update={"bars_held": len(future_bars)})

    last = future_bars[-1]
    if probe.side == Side.BUY:
        exit_price = last.close
        result_r = (exit_price - probe.entry_price) / probe.risk_distance
    else:
        exit_price = last.close + probe.spread_at_entry
        result_r = (probe.entry_price - exit_price) / probe.risk_distance

    return _close_probe(
        probe,
        status=PaperTradeStatus.TIMEOUT,
        exit_at=last.timestamp,
        exit_price=exit_price,
        result_r=result_r,
        bars_held=probe.max_holding_bars,
    )


def _next_full_m5_bar_start(at: datetime) -> datetime:
    minute_floor = at.replace(second=0, microsecond=0)
    remainder = minute_floor.minute % 5
    if remainder == 0 and at.second == 0 and at.microsecond == 0:
        return minute_floor
    minutes = 5 - remainder if remainder else 5
    return minute_floor + timedelta(minutes=minutes)


def _close_probe(
    probe: BlockedOpportunityProbe,
    *,
    status: PaperTradeStatus,
    exit_at: datetime,
    exit_price: float,
    result_r: float,
    bars_held: int,
) -> BlockedOpportunityProbe:
    return probe.model_copy(
        update={
            "status": status,
            "exit_at": exit_at,
            "exit_price": exit_price,
            "result_r": result_r,
            "bars_held": bars_held,
        }
    )


def load_blocked_probe_state(path: Path) -> BlockedProbeState:
    if not path.is_file():
        return BlockedProbeState()
    try:
        return BlockedProbeState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return BlockedProbeState()


def save_blocked_probe_state(path: Path, state: BlockedProbeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def append_closed_probe(path: Path, probe: BlockedOpportunityProbe) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(probe.model_dump_json())
        handle.write("\n")


def load_closed_probes(path: Path) -> list[BlockedOpportunityProbe]:
    if not path.is_file():
        return []
    probes: list[BlockedOpportunityProbe] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                probe = BlockedOpportunityProbe.model_validate_json(line)
            except ValueError:
                continue
            if probe.status != PaperTradeStatus.OPEN:
                probes.append(probe)
    return probes


def load_blocked_probe_summary(
    state_path: Path,
    probes_path: Path,
) -> BlockedProbeSummary:
    state = load_blocked_probe_state(state_path)
    probes = load_closed_probes(probes_path)
    results = [
        probe.result_r for probe in probes if probe.result_r is not None
    ]
    gains = sum(result for result in results if result > 0)
    losses = -sum(result for result in results if result < 0)
    profit_factor = gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)

    return BlockedProbeSummary(
        closed_probes=len(probes),
        wins=sum(result > 0 for result in results),
        losses=sum(result < 0 for result in results),
        total_r=sum(results),
        expectancy_r=(sum(results) / len(results)) if results else 0.0,
        profit_factor=profit_factor,
        open_probe=state.open_probe,
        recent_probes=probes[-RECENT_PROBES_LIMIT:][::-1],
    )
