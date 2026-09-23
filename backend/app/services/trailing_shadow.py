import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.domain.market import Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.trailing_manager import TrailingManagerConfig
from app.domain.trailing_shadow import (
    TrailingShadowEvaluation,
    TrailingShadowState,
    TrailingShadowSummary,
)
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.shadow_paper import load_closed_trades
from app.services.trailing_manager import replay_trailing_trade

STRATEGY_ID = "BTCUSD:structural_displacement_sequence"
SYMBOL = "BTCUSD"
STATE_FILE = "BTCUSD_structural_displacement_sequence_trailing_shadow_state.json"
LEDGER_FILE = "BTCUSD_structural_displacement_sequence_trailing_shadow.jsonl"
PAPER_TRADES_FILE = "BTCUSD_structural_displacement_sequence_paper_trades.jsonl"
POLICY = TrailingManagerConfig(
    enable_stop_trailing=False,
    enable_target_extension=True,
    target_extension_requires_protected_stop=False,
)


def advance_trailing_shadow_once(
    files_dir: Path,
    runtime_dir: Path,
    evaluated_at: datetime,
) -> TrailingShadowSummary:
    state_path = runtime_dir / STATE_FILE
    ledger_path = runtime_dir / LEDGER_FILE
    state = load_trailing_shadow_state(state_path)
    if state is None:
        state = TrailingShadowState(started_at=evaluated_at)
        save_trailing_shadow_state(state_path, state)
        return load_trailing_shadow_summary(runtime_dir)

    m5_path = resolve_mt4_history_path(files_dir, SYMBOL, Timeframe.M5)
    if m5_path is None:
        return load_trailing_shadow_summary(runtime_dir)
    bars = read_mt4_csv(m5_path, SYMBOL, Timeframe.M5)
    if not bars:
        return load_trailing_shadow_summary(runtime_dir)

    existing_ids = {
        row.trade_id for row in load_trailing_shadow_evaluations(ledger_path)
    }
    trades = load_closed_trades(runtime_dir / PAPER_TRADES_FILE)
    for trade in trades:
        if trade.trade_id in existing_ids:
            continue
        if trade.symbol.upper() != SYMBOL:
            continue
        if trade.mechanism != OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE:
            continue
        if trade.opened_at < state.started_at:
            continue
        if trade.result_r is None or trade.pnl_eur is None:
            continue

        replay_bars = [
            bar for bar in bars if bar.timestamp >= trade.entry_bar_at
        ]
        if len(replay_bars) < trade.max_holding_bars:
            continue

        replay = replay_trailing_trade(
            trade,
            replay_bars,
            config=POLICY,
        )
        evaluation = TrailingShadowEvaluation(
            trade_id=trade.trade_id,
            evaluated_at=evaluated_at,
            static_result_r=trade.result_r,
            trailing_result_r=replay.result_r,
            delta_r=replay.result_r - trade.result_r,
            static_pnl_eur=trade.pnl_eur,
            trailing_pnl_eur=replay.pnl_eur,
            adjustments=len(replay.adjustments),
            exit_reason=replay.exit_reason,
        )
        append_trailing_shadow_evaluation(ledger_path, evaluation)
        existing_ids.add(trade.trade_id)

    return load_trailing_shadow_summary(runtime_dir)


def load_trailing_shadow_state(path: Path) -> TrailingShadowState | None:
    if not path.is_file():
        return None
    try:
        return TrailingShadowState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def save_trailing_shadow_state(
    path: Path,
    state: TrailingShadowState,
) -> None:
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


def append_trailing_shadow_evaluation(
    path: Path,
    evaluation: TrailingShadowEvaluation,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(evaluation.model_dump_json())
        handle.write("\n")


def load_trailing_shadow_evaluations(
    path: Path,
) -> list[TrailingShadowEvaluation]:
    if not path.is_file():
        return []
    rows: list[TrailingShadowEvaluation] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    TrailingShadowEvaluation.model_validate(
                        json.loads(line)
                    )
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def load_trailing_shadow_summary(runtime_dir: Path) -> TrailingShadowSummary:
    state = load_trailing_shadow_state(runtime_dir / STATE_FILE)
    rows = load_trailing_shadow_evaluations(runtime_dir / LEDGER_FILE)
    deltas = [row.delta_r for row in rows]
    return TrailingShadowSummary(
        strategy_id=STRATEGY_ID,
        started_at=state.started_at if state is not None else None,
        resolved=len(rows),
        improved=sum(delta > 1e-12 for delta in deltas),
        worsened=sum(delta < -1e-12 for delta in deltas),
        unchanged=sum(abs(delta) <= 1e-12 for delta in deltas),
        static_total_r=sum(row.static_result_r for row in rows),
        trailing_total_r=sum(row.trailing_result_r for row in rows),
        expectancy_delta_r=(
            sum(deltas) / len(deltas) if deltas else 0.0
        ),
        total_adjustments=sum(row.adjustments for row in rows),
        recent=rows[-10:][::-1],
    )
