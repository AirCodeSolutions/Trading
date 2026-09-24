from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.domain.market import Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    ResearchSplit,
)
from app.domain.precursor_execution_shadow import (
    PrecursorExecutionShadowRow,
    PrecursorExecutionShadowState,
    PrecursorExecutionShadowSummary,
)
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.causal_precursor import load_causal_precursors
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.mt4_specs import get_mt4_symbol_spec
from app.services.opportunity_backtester import _simulate_candidate
from app.services.opportunity_strategies import _atr_series
from app.services.research_execution_model import (
    apply_research_execution_model,
    load_research_execution_model,
)
from app.services.runtime_capital import resolve_demo_sizing_capital

SYMBOL = "XAUUSD"
PATTERN = OpportunityCausalPattern.COMPRESSION_BREAKOUT
STRATEGY_ID = "XAUUSD:precursor_compression_breakout_shadow"
STATE_FILE = "XAUUSD_precursor_compression_shadow_state.json"
LEDGER_FILE = "XAUUSD_precursor_compression_shadow.jsonl"
HORIZON_BARS = 12
STOP_ATR_MULTIPLE = 1.5
TARGET_R = 1.0


def advance_xau_compression_precursor_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
) -> PrecursorExecutionShadowSummary:
    state_path = runtime_dir / STATE_FILE
    ledger_path = runtime_dir / LEDGER_FILE
    state = load_precursor_shadow_state(state_path)
    if state is None:
        state = PrecursorExecutionShadowState(started_at=evaluated_at)
        save_precursor_shadow_state(state_path, state)
        return load_xau_compression_precursor_shadow_summary(runtime_dir)

    capital = resolve_demo_sizing_capital(files_dir)
    if capital.capital_eur is None or capital.is_demo is not True:
        return load_xau_compression_precursor_shadow_summary(runtime_dir)

    observations = load_causal_precursors(
        runtime_dir,
        window_start=state.started_at,
        window_end=evaluated_at,
        symbols=(SYMBOL,),
    )
    observations = [
        row
        for row in observations
        if row.pattern == PATTERN and row.first_seen_at >= state.started_at
    ]
    if not observations:
        return load_xau_compression_precursor_shadow_summary(runtime_dir)

    elapsed_minutes = max(
        0.0,
        (evaluated_at - state.started_at).total_seconds() / 60.0,
    )
    bars = load_recent_closed_market_bars(
        files_dir,
        SYMBOL,
        Timeframe.M5,
        evaluated_at,
        limit=max(100, int(elapsed_minutes / 5) + HORIZON_BARS + 64),
    )
    if len(bars) < 30:
        return load_xau_compression_precursor_shadow_summary(runtime_dir)

    by_timestamp = {bar.timestamp: index for index, bar in enumerate(bars)}
    atr = _atr_series(bars)
    existing_ids = {
        row.precursor_id
        for row in load_precursor_shadow_rows(ledger_path)
    }

    raw_spec = get_mt4_symbol_spec(files_dir, SYMBOL)
    if raw_spec is None:
        return load_xau_compression_precursor_shadow_summary(runtime_dir)
    execution_model = load_research_execution_model(
        settings.research_execution_model_path
    )
    spec = apply_research_execution_model(raw_spec, execution_model)
    macro_events = load_macro_events(settings.macro_events_path)
    split = ResearchSplit(
        train_end=evaluated_at - timedelta(days=2),
        validation_end=evaluated_at - timedelta(days=1),
    )
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        split=split,
        capital_eur=capital.capital_eur,
        macro_events=macro_events,
    )

    for observation in observations:
        precursor_id = f"{SYMBOL}:{PATTERN.value}:{observation.first_seen_at.isoformat()}"
        if precursor_id in existing_ids:
            continue
        index = by_timestamp.get(observation.latest_closed_m5_at)
        if index is None or index >= len(atr) or atr[index] <= 0:
            continue
        entry_index = index + 1
        final_index = entry_index + HORIZON_BARS - 1
        if entry_index >= len(bars) or final_index >= len(bars):
            continue

        entry = bars[entry_index].open
        stop_distance = STOP_ATR_MULTIPLE * atr[index]
        stop = (
            entry - stop_distance
            if observation.side.value == "buy"
            else entry + stop_distance
        )
        if stop <= 0:
            continue

        candidate = OpportunityCandidate(
            symbol=SYMBOL,
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=observation.side,
            signal_at=observation.first_seen_at,
            entry_at=bars[entry_index].timestamp,
            signal_index=index,
            entry_index=entry_index,
            structural_stop=stop,
            target_r=TARGET_R,
            max_holding_bars=HORIZON_BARS,
            reason="prospective XAU compression-breakout precursor shadow",
        )
        if active_macro_blackouts(macro_events, candidate.entry_at):
            continue
        outcome, _, rejection = _simulate_candidate(
            bars,
            candidate,
            config,
        )
        if rejection is not None or outcome is None:
            continue

        append_precursor_shadow_row(
            ledger_path,
            PrecursorExecutionShadowRow(
                precursor_id=precursor_id,
                first_seen_at=observation.first_seen_at,
                outcome=outcome,
            ),
        )
        existing_ids.add(precursor_id)

    return load_xau_compression_precursor_shadow_summary(runtime_dir)


def load_precursor_shadow_state(
    path: Path,
) -> PrecursorExecutionShadowState | None:
    if not path.is_file():
        return None
    try:
        return PrecursorExecutionShadowState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def save_precursor_shadow_state(
    path: Path,
    state: PrecursorExecutionShadowState,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_precursor_shadow_rows(
    path: Path,
) -> list[PrecursorExecutionShadowRow]:
    if not path.is_file():
        return []
    rows: list[PrecursorExecutionShadowRow] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    PrecursorExecutionShadowRow.model_validate(json.loads(line))
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def append_precursor_shadow_row(
    path: Path,
    row: PrecursorExecutionShadowRow,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row.model_dump_json())
        handle.write("\n")


def load_xau_compression_precursor_shadow_summary(
    runtime_dir: Path,
) -> PrecursorExecutionShadowSummary:
    state = load_precursor_shadow_state(runtime_dir / STATE_FILE)
    rows = load_precursor_shadow_rows(runtime_dir / LEDGER_FILE)
    values = [row.outcome.result_r for row in rows]
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return PrecursorExecutionShadowSummary(
        strategy_id=STRATEGY_ID,
        started_at=state.started_at if state is not None else None,
        resolved=len(rows),
        wins=sum(value > 0 for value in values),
        losses=sum(value <= 0 for value in values),
        total_r=sum(values),
        expectancy_r=(sum(values) / len(values) if values else 0.0),
        profit_factor=(
            gross_profit / gross_loss
            if gross_loss > 0
            else (99.0 if gross_profit > 0 else 0.0)
        ),
        max_drawdown_r=max_drawdown,
        recent=rows[-10:][::-1],
    )
