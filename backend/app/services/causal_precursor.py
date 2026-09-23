from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.domain.causal_precursor import (
    CausalPrecursorCollectionState,
    CausalPrecursorObservation,
)
from app.domain.market import Timeframe
from app.domain.trading import Side
from app.services.mt4_market_data import load_closed_market_bars

PRECURSOR_COLLECTION_STATE_FILE = "causal_precursor_collection_state.json"
PRECURSOR_LEDGER_SUFFIX = "_causal_precursors.jsonl"


def advance_causal_precursors_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
    *,
    symbols: Iterable[str],
) -> int:
    if evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    from app.services.trading_intelligence import (
        _atr_series,
        _classify_causal_context,
    )

    _ensure_collection_state(runtime_dir, evaluated_at)
    appended = 0
    for symbol in symbols:
        normalized = symbol.upper()
        bars = load_closed_market_bars(
            files_dir,
            normalized,
            Timeframe.M5,
            evaluated_at,
        )
        if len(bars) < 30:
            continue

        atr = _atr_series(bars)
        index = len(bars) - 1
        context = _classify_causal_context(
            bars=bars,
            atr=atr,
            index=index,
            episode_side=Side.BUY,
        ).model_copy(update={"aligned_with_move": None})
        if context.side is None:
            continue

        latest = bars[index]
        first_seen_at = latest.timestamp + timedelta(minutes=5)
        if first_seen_at > evaluated_at + timedelta(minutes=1):
            continue

        observation = CausalPrecursorObservation(
            symbol=normalized,
            first_seen_at=first_seen_at,
            latest_closed_m5_at=latest.timestamp,
            pattern=context.pattern,
            side=context.side,
            context=context,
        )
        path = runtime_dir / f"{normalized}{PRECURSOR_LEDGER_SUFFIX}"
        if append_causal_precursor_if_new(path, observation):
            appended += 1
    return appended


def append_causal_precursor_if_new(
    path: Path,
    observation: CausalPrecursorObservation,
) -> bool:
    last = _read_last_observation(path)
    if (
        last is not None
        and last.latest_closed_m5_at == observation.latest_closed_m5_at
    ):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(observation.model_dump_json())
        handle.write("\n")
    return True


def load_causal_precursors(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    symbols: Iterable[str] | None = None,
) -> list[CausalPrecursorObservation]:
    allowed = {symbol.upper() for symbol in symbols} if symbols else None
    rows: list[CausalPrecursorObservation] = []
    for path in sorted(runtime_dir.glob(f"*{PRECURSOR_LEDGER_SUFFIX}")):
        symbol = path.name.removesuffix(PRECURSOR_LEDGER_SUFFIX).upper()
        if allowed is not None and symbol not in allowed:
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = CausalPrecursorObservation.model_validate_json(line)
                except ValueError:
                    continue
                if window_start <= row.first_seen_at <= window_end:
                    rows.append(row)
    rows.sort(key=lambda row: row.first_seen_at)
    return rows


def load_causal_precursor_collection_state(
    runtime_dir: Path,
) -> CausalPrecursorCollectionState | None:
    path = runtime_dir / PRECURSOR_COLLECTION_STATE_FILE
    if not path.is_file():
        return None
    try:
        return CausalPrecursorCollectionState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def _ensure_collection_state(
    runtime_dir: Path,
    evaluated_at: datetime,
) -> CausalPrecursorCollectionState:
    current = load_causal_precursor_collection_state(runtime_dir)
    if current is not None:
        return current

    state = CausalPrecursorCollectionState(started_at=evaluated_at)
    path = runtime_dir / PRECURSOR_COLLECTION_STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return state


def _read_last_observation(
    path: Path,
) -> CausalPrecursorObservation | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            return CausalPrecursorObservation.model_validate_json(line)
        except ValueError:
            continue
    return None
