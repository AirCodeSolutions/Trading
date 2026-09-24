import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.xau_microbar import (
    XauMicrobarGeometry,
    XauMicrobarM1,
    XauMicrobarState,
    XauMicrobarSummary,
    XauSequenceMicrostructureSnapshot,
)
from app.services.mt4_csv import mt4_epoch_to_server_datetime

SYMBOL = "XAUUSD"
STATE_FILE = "XAUUSD_micro_m1_state.json"
LEDGER_FILE = "XAUUSD_micro_m1.jsonl"
SEQUENCE_SNAPSHOT_FILE = "XAUUSD_sequence_microstructure.jsonl"
MAX_SAMPLE_AGE_SECONDS = 15.0
RECENT_LIMIT = 20
SEQUENCE_RECENT_LIMIT = 10
SEQUENCE_MECHANISMS = {
    OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
}


def sample_xau_microbar_once(
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
) -> XauMicrobarSummary:
    state_path = runtime_dir / STATE_FILE
    ledger_path = runtime_dir / LEDGER_FILE
    state = load_xau_microbar_state(state_path)
    if state is None:
        state = XauMicrobarState(started_at=now)

    quote = read_xau_quote(files_dir)
    if quote is not None:
        quote_at, bid, ask = quote
        age = max(0.0, (now - quote_at).total_seconds())
        if (
            age <= MAX_SAMPLE_AGE_SECONDS
            and (
                state.last_quote_at is None
                or quote_at > state.last_quote_at
            )
        ):
            state = _apply_quote(state, quote_at, bid, ask, ledger_path)

    save_xau_microbar_state(state_path, state)
    return load_xau_microbar_summary(runtime_dir, now=now)


def read_xau_quote(
    files_dir: Path,
) -> tuple[datetime, float, float] | None:
    path = files_dir / "trading_demo_spec_XAUUSD.csv"
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None
    if not rows:
        return None

    row = rows[-1]
    try:
        if str(row.get("symbol", "")).strip().upper() != SYMBOL:
            return None
        quote_at = mt4_epoch_to_server_datetime(int(str(row["timestamp"])))
        bid = float(str(row["bid"]))
        ask = float(str(row["ask"]))
    except (KeyError, TypeError, ValueError):
        return None
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return quote_at, bid, ask


def _apply_quote(
    state: XauMicrobarState,
    quote_at: datetime,
    bid: float,
    ask: float,
    ledger_path: Path,
) -> XauMicrobarState:
    minute_at = quote_at.replace(second=0, microsecond=0)
    current = state.current_bar

    if current is None:
        current = _new_bar(minute_at, quote_at, bid, ask)
    elif minute_at == current.minute_at:
        current = _update_bar(current, quote_at, bid, ask)
    elif minute_at > current.minute_at:
        append_xau_microbar(ledger_path, current)
        current = _new_bar(minute_at, quote_at, bid, ask)
    else:
        return state

    return state.model_copy(
        update={
            "last_quote_at": quote_at,
            "total_quote_samples": state.total_quote_samples + 1,
            "current_bar": current,
        }
    )


def _new_bar(
    minute_at: datetime,
    quote_at: datetime,
    bid: float,
    ask: float,
) -> XauMicrobarM1:
    mid = (bid + ask) / 2
    spread = ask - bid
    return XauMicrobarM1(
        minute_at=minute_at,
        first_quote_at=quote_at,
        last_quote_at=quote_at,
        bid_open=bid,
        bid_high=bid,
        bid_low=bid,
        bid_close=bid,
        ask_open=ask,
        ask_high=ask,
        ask_low=ask,
        ask_close=ask,
        mid_open=mid,
        mid_high=mid,
        mid_low=mid,
        mid_close=mid,
        spread_open=spread,
        spread_high=spread,
        spread_low=spread,
        spread_close=spread,
        spread_sum=spread,
        quote_count=1,
    )


def _update_bar(
    bar: XauMicrobarM1,
    quote_at: datetime,
    bid: float,
    ask: float,
) -> XauMicrobarM1:
    mid = (bid + ask) / 2
    spread = ask - bid
    return bar.model_copy(
        update={
            "last_quote_at": quote_at,
            "bid_high": max(bar.bid_high, bid),
            "bid_low": min(bar.bid_low, bid),
            "bid_close": bid,
            "ask_high": max(bar.ask_high, ask),
            "ask_low": min(bar.ask_low, ask),
            "ask_close": ask,
            "mid_high": max(bar.mid_high, mid),
            "mid_low": min(bar.mid_low, mid),
            "mid_close": mid,
            "spread_high": max(bar.spread_high, spread),
            "spread_low": min(bar.spread_low, spread),
            "spread_close": spread,
            "spread_sum": bar.spread_sum + spread,
            "quote_count": bar.quote_count + 1,
        }
    )


def load_xau_microbar_state(path: Path) -> XauMicrobarState | None:
    if not path.is_file():
        return None
    try:
        return XauMicrobarState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def save_xau_microbar_state(
    path: Path,
    state: XauMicrobarState,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def append_xau_microbar(path: Path, bar: XauMicrobarM1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(bar.model_dump_json())
        handle.write("\n")


def load_xau_microbars(path: Path) -> list[XauMicrobarM1]:
    if not path.is_file():
        return []
    rows: list[XauMicrobarM1] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    XauMicrobarM1.model_validate(json.loads(line))
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def _geometry_window(
    rows: list[XauMicrobarM1],
    window_minutes: int,
) -> XauMicrobarGeometry | None:
    if not rows:
        return None

    selected = rows[-window_minutes:]
    first = selected[0]
    last = selected[-1]
    mid_high = max(row.mid_high for row in selected)
    mid_low = min(row.mid_low for row in selected)
    range_price = max(0.0, mid_high - mid_low)
    signed_move = last.mid_close - first.mid_open
    points = [first.mid_open, *(row.mid_close for row in selected)]
    path = sum(
        abs(points[index] - points[index - 1])
        for index in range(1, len(points))
    )
    path_efficiency = min(
        1.0,
        abs(signed_move) / path if path > 0 else 0.0,
    )
    close_location = (
        (last.mid_close - mid_low) / range_price
        if range_price > 0
        else 0.5
    )
    total_quotes = sum(row.quote_count for row in selected)
    total_spread = sum(row.spread_sum for row in selected)

    return XauMicrobarGeometry(
        window_minutes=window_minutes,
        bars=len(selected),
        start_at=first.minute_at,
        end_at=last.minute_at + timedelta(minutes=1),
        mid_open=first.mid_open,
        mid_high=mid_high,
        mid_low=mid_low,
        mid_close=last.mid_close,
        range_price=range_price,
        signed_move=signed_move,
        close_location=min(1.0, max(0.0, close_location)),
        path_efficiency=path_efficiency,
        average_spread=(total_spread / total_quotes if total_quotes else 0.0),
        max_spread=max(row.spread_high for row in selected),
        average_quotes_per_bar=total_quotes / len(selected),
        distance_to_low=max(0.0, last.mid_close - mid_low),
        distance_to_high=max(0.0, mid_high - last.mid_close),
    )


def load_xau_sequence_microstructure_snapshots(
    path: Path,
) -> list[XauSequenceMicrostructureSnapshot]:
    if not path.is_file():
        return []
    rows: list[XauSequenceMicrostructureSnapshot] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    XauSequenceMicrostructureSnapshot.model_validate(
                        json.loads(line)
                    )
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def append_xau_sequence_microstructure_snapshot(
    path: Path,
    snapshot: XauSequenceMicrostructureSnapshot,
) -> bool:
    existing = load_xau_sequence_microstructure_snapshots(path)
    key = (snapshot.strategy_id, snapshot.signal_at)
    if any((row.strategy_id, row.signal_at) == key for row in existing):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(snapshot.model_dump_json())
        handle.write("\n")
    return True


def capture_xau_sequence_microstructure(
    runtime_dir: Path,
    diagnostic: ShadowOpportunityDiagnostic,
) -> bool:
    if diagnostic.symbol.upper() != SYMBOL:
        return False
    if diagnostic.mechanism not in SEQUENCE_MECHANISMS:
        return False
    if diagnostic.state == ShadowSignalState.NO_SIGNAL:
        return False

    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    rows = [
        row
        for row in load_xau_microbars(runtime_dir / LEDGER_FILE)
        if row.minute_at + timedelta(minutes=1) <= signal_at
    ]
    latest_microbar_at = rows[-1].minute_at if rows else None
    strategy_id = f"{diagnostic.symbol}:{diagnostic.mechanism.value}"
    snapshot = XauSequenceMicrostructureSnapshot(
        strategy_id=strategy_id,
        mechanism=diagnostic.mechanism,
        signal_at=signal_at,
        evaluated_at=diagnostic.evaluated_at,
        state=diagnostic.state,
        side=diagnostic.side,
        latest_microbar_at=latest_microbar_at,
        geometry_5m=_geometry_window(rows, 5),
        geometry_15m=_geometry_window(rows, 15),
    )
    return append_xau_sequence_microstructure_snapshot(
        runtime_dir / SEQUENCE_SNAPSHOT_FILE,
        snapshot,
    )


def load_xau_microbar_summary(
    runtime_dir: Path,
    *,
    now: datetime,
) -> XauMicrobarSummary:
    state = load_xau_microbar_state(runtime_dir / STATE_FILE)
    rows = load_xau_microbars(runtime_dir / LEDGER_FILE)
    snapshots = load_xau_sequence_microstructure_snapshots(
        runtime_dir / SEQUENCE_SNAPSHOT_FILE
    )
    last_quote_at = state.last_quote_at if state is not None else None
    quote_age = (
        max(0.0, (now - last_quote_at).total_seconds())
        if last_quote_at is not None
        else None
    )
    return XauMicrobarSummary(
        started_at=state.started_at if state is not None else None,
        healthy=bool(
            quote_age is not None
            and quote_age <= MAX_SAMPLE_AGE_SECONDS
        ),
        quote_age_seconds=quote_age,
        last_quote_at=last_quote_at,
        total_quote_samples=(
            state.total_quote_samples if state is not None else 0
        ),
        closed_bars=len(rows),
        latest_closed_bar_at=(rows[-1].minute_at if rows else None),
        current_bar=(state.current_bar if state is not None else None),
        geometry_5m=_geometry_window(rows, 5),
        geometry_15m=_geometry_window(rows, 15),
        sequence_signal_snapshots=len(snapshots),
        recent_sequence_signals=snapshots[-SEQUENCE_RECENT_LIMIT:][::-1],
        recent=rows[-RECENT_LIMIT:][::-1],
    )
