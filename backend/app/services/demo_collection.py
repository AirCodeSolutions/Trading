from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.demo_collection import DemoCollectionState
from app.domain.demo_execution import (
    DemoBridgeCommandStatus,
    DemoBridgePosition,
)
from app.domain.macro import MacroGateStatus
from app.domain.market import Timeframe
from app.domain.portfolio import (
    PaperStrategyRuntime,
    PortfolioAction,
    TradingOverview,
)
from app.domain.shadow_paper import ShadowPaperTrade
from app.services.demo_execution import (
    CLOSE_COMMAND_FILE,
    COMMAND_FILE,
    POSITIONS_FILE,
    RESULT_FILE,
    read_demo_positions,
    read_demo_result,
    read_pending_close_command,
    read_pending_command,
    submit_demo_close_order,
    submit_selected_demo_order,
)

STATE_FILE = "demo_collection_state.json"
TRADING_NEW_COMMENT_PREFIX = "TradingNew:"
MAX_COMPLETED_TRADE_IDS = 200


def advance_demo_collection(
    files_dir: Path,
    runtime_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
    *,
    allow_new_entries: bool = True,
) -> DemoCollectionState:
    state_path = runtime_dir / STATE_FILE
    state = load_demo_collection_state(state_path)
    positions = read_demo_positions(files_dir / POSITIONS_FILE)
    result = read_demo_result(files_dir / RESULT_FILE)

    matched_open_result = bool(
        state.open_command_id
        and result is not None
        and result.command_id == state.open_command_id
    )
    state = _consume_open_result(state, result)
    if matched_open_result:
        save_demo_collection_state(state_path, state)
        return state

    matched_close_result = bool(
        state.close_command_id
        and result is not None
        and result.command_id == state.close_command_id
    )
    state = _consume_close_result(state, result, positions)
    if matched_close_result:
        save_demo_collection_state(state_path, state)
        return state

    # The bridge transports exactly one file command at a time. Multiple filled
    # positions are allowed, but command transport stays serialized.
    if read_pending_command(files_dir / COMMAND_FILE) is not None:
        save_demo_collection_state(state_path, state)
        return state
    if read_pending_close_command(files_dir / CLOSE_COMMAND_FILE) is not None:
        save_demo_collection_state(state_path, state)
        return state

    close_target = _next_managed_position_to_close(overview, positions)
    if close_target is not None:
        position, strategy_id = close_target
        try:
            command = submit_demo_close_order(
                files_dir=files_dir,
                overview=overview,
                ticket=position.ticket,
                strategy_id=strategy_id,
                now=now,
                audit_path=runtime_dir / "demo_execution_audit.jsonl",
            )
        except ValueError as exc:
            state.last_error = str(exc)
        else:
            state.paper_trade_id = None
            state.open_command_id = None
            state.ticket = position.ticket
            state.strategy_id = strategy_id
            state.close_command_id = command.command_id
            state.last_error = None
        save_demo_collection_state(state_path, state)
        return state

    if not allow_new_entries:
        save_demo_collection_state(state_path, state)
        return state

    candidate = _next_open_candidate(
        overview,
        positions,
        completed_trade_ids=set(state.completed_trade_ids),
    )
    if candidate is None:
        save_demo_collection_state(state_path, state)
        return state

    row, trade = candidate
    proposal = ExecutionProposal(
        id=f"demo-collection-{trade.trade_id}",
        symbol=trade.symbol,
        timeframe=Timeframe.M5,
        side=trade.side,
        strategy_id=row.strategy_id,
        at=trade.signal_at,
        reason="automatic multi-symbol broker DEMO collection",
        status=ProposalStatus.AUTHORIZED,
    )
    try:
        command = submit_selected_demo_order(
            files_dir=files_dir,
            overview=overview,
            macro=macro,
            proposal=proposal,
            now=now,
            audit_path=runtime_dir / "demo_execution_audit.jsonl",
        )
    except ValueError as exc:
        state.last_error = str(exc)
    else:
        state.paper_trade_id = trade.trade_id
        state.strategy_id = row.strategy_id
        state.open_command_id = command.command_id
        state.ticket = None
        state.close_command_id = None
        state.last_error = None

    save_demo_collection_state(state_path, state)
    return state


def load_demo_collection_state(path: Path) -> DemoCollectionState:
    if not path.is_file():
        return DemoCollectionState()
    try:
        return DemoCollectionState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return DemoCollectionState()


def save_demo_collection_state(
    path: Path,
    state: DemoCollectionState,
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


def _consume_open_result(
    state: DemoCollectionState,
    result,
) -> DemoCollectionState:
    if (
        state.open_command_id is None
        or result is None
        or result.command_id != state.open_command_id
    ):
        return state

    trade_id = state.paper_trade_id
    if result.status == DemoBridgeCommandStatus.FILLED and result.ticket > 0:
        state = _mark_completed(state, trade_id)
        state.paper_trade_id = None
        state.strategy_id = None
        state.open_command_id = None
        state.ticket = None
        state.last_error = None
        return state

    if result.status in {
        DemoBridgeCommandStatus.REFUSED,
        DemoBridgeCommandStatus.ERROR,
    }:
        state = _mark_completed(state, trade_id)
        state.paper_trade_id = None
        state.strategy_id = None
        state.open_command_id = None
        state.ticket = None
        state.last_error = (
            f"open {result.status.value} error={result.error_code}"
        )
    return state


def _consume_close_result(
    state: DemoCollectionState,
    result,
    positions: list[DemoBridgePosition],
) -> DemoCollectionState:
    if (
        state.close_command_id is None
        or result is None
        or result.command_id != state.close_command_id
    ):
        return state

    if result.status == DemoBridgeCommandStatus.FILLED:
        if state.ticket is None or not any(
            position.ticket == state.ticket for position in positions
        ):
            state.ticket = None
            state.strategy_id = None
            state.close_command_id = None
            state.last_error = None
        return state

    if result.status in {
        DemoBridgeCommandStatus.REFUSED,
        DemoBridgeCommandStatus.ERROR,
    }:
        state.ticket = None
        state.strategy_id = None
        state.close_command_id = None
        state.last_error = (
            f"close {result.status.value} error={result.error_code}"
        )
    return state


def _next_open_candidate(
    overview: TradingOverview,
    positions: list[DemoBridgePosition],
    *,
    completed_trade_ids: set[str],
) -> tuple[PaperStrategyRuntime, ShadowPaperTrade] | None:
    occupied_symbols = {
        position.symbol.upper()
        for position in positions
    }
    candidates: list[tuple[PaperStrategyRuntime, ShadowPaperTrade]] = []
    for row in overview.paper_strategies:
        trade = row.summary.open_trade
        selected_legacy_entry = (
            row.strategy_id == overview.portfolio.selected_strategy_id
            and overview.portfolio.action
            in {
                PortfolioAction.DEMO_COLLECTION,
                PortfolioAction.DEMO_ELIGIBLE,
            }
        )
        if (
            trade is None
            or not (row.paper_entry_allowed or selected_legacy_entry)
        ):
            continue
        if trade.symbol.upper() in occupied_symbols:
            continue
        if trade.trade_id in completed_trade_ids:
            continue
        candidates.append((row, trade))

    if not candidates:
        return None

    # Oldest still-open signal first, deterministic on strategy id.
    return min(
        candidates,
        key=lambda pair: (
            pair[1].signal_at,
            pair[0].strategy_id,
        ),
    )


def _next_managed_position_to_close(
    overview: TradingOverview,
    positions: list[DemoBridgePosition],
) -> tuple[DemoBridgePosition, str] | None:
    rows_by_strategy = {
        row.strategy_id: row
        for row in overview.paper_strategies
    }
    candidates: list[tuple[DemoBridgePosition, str]] = []

    for position in positions:
        strategy_id = _strategy_id_from_position(position)
        if strategy_id is None:
            continue
        row = rows_by_strategy.get(strategy_id)
        # Unknown/manual Trading-New positions are intentionally never touched.
        if row is None:
            continue
        if row.summary.open_trade is None:
            candidates.append((position, strategy_id))

    if not candidates:
        return None
    return min(candidates, key=lambda pair: pair[0].ticket)


def _strategy_id_from_position(
    position: DemoBridgePosition,
) -> str | None:
    comment = position.strategy_comment
    if not comment.startswith(TRADING_NEW_COMMENT_PREFIX):
        return None
    strategy_id = comment.removeprefix(TRADING_NEW_COMMENT_PREFIX).strip()
    return strategy_id or None


def _mark_completed(
    state: DemoCollectionState,
    trade_id: str | None,
) -> DemoCollectionState:
    if trade_id is None:
        return state
    completed = [
        item
        for item in state.completed_trade_ids
        if item != trade_id
    ]
    completed.append(trade_id)
    state.completed_trade_ids = completed[-MAX_COMPLETED_TRADE_IDS:]
    state.last_completed_trade_id = trade_id
    return state
