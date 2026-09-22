from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.demo_collection import DemoCollectionState
from app.domain.demo_execution import DemoBridgeCommandStatus
from app.domain.macro import MacroGateStatus
from app.domain.market import Timeframe
from app.domain.portfolio import PortfolioAction, TradingOverview
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
from app.services.shadow_paper import load_closed_trades

STATE_FILE = "demo_collection_state.json"


def advance_demo_collection(
    files_dir: Path,
    runtime_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
) -> DemoCollectionState:
    state_path = runtime_dir / STATE_FILE
    state = load_demo_collection_state(state_path)
    positions = read_demo_positions(files_dir / POSITIONS_FILE)
    result = read_demo_result(files_dir / RESULT_FILE)

    if state.open_command_id and result is not None and result.command_id == state.open_command_id:
        if result.status == DemoBridgeCommandStatus.FILLED and result.ticket > 0:
            state.ticket = result.ticket
            state.last_error = None
        elif result.status in {
            DemoBridgeCommandStatus.REFUSED,
            DemoBridgeCommandStatus.ERROR,
        }:
            state = _complete_state(
                state,
                error=f"open {result.status.value} error={result.error_code}",
            )
            save_demo_collection_state(state_path, state)
            return state

    if state.paper_trade_id and state.ticket is None and len(positions) == 1:
        state.ticket = positions[0].ticket

    if (
        state.close_command_id
        and result is not None
        and result.command_id == state.close_command_id
    ):
        if result.status == DemoBridgeCommandStatus.FILLED:
            if _bridge_position_for_state(positions, state) is None:
                state = _complete_state(state)
            save_demo_collection_state(state_path, state)
            return state
        if result.status in {
            DemoBridgeCommandStatus.REFUSED,
            DemoBridgeCommandStatus.ERROR,
        }:
            state.last_error = (
                f"close {result.status.value} error={result.error_code}"
            )
            state.close_command_id = None

    active_paper = _find_open_paper_trade(overview, state.paper_trade_id)
    if state.paper_trade_id is not None:
        if active_paper is not None:
            save_demo_collection_state(state_path, state)
            return state

        closed = _find_closed_paper_trade(runtime_dir, state.paper_trade_id)
        position = _bridge_position_for_state(positions, state)
        if position is None:
            state = _complete_state(state)
            save_demo_collection_state(state_path, state)
            return state

        if closed is not None:
            pending_close = read_pending_close_command(files_dir / CLOSE_COMMAND_FILE)
            if pending_close is None:
                try:
                    command = submit_demo_close_order(
                        files_dir=files_dir,
                        overview=overview,
                        ticket=position.ticket,
                        strategy_id=state.strategy_id or closed.mechanism.value,
                        now=now,
                        audit_path=runtime_dir / "demo_execution_audit.jsonl",
                    )
                except ValueError as exc:
                    state.last_error = str(exc)
                else:
                    state.ticket = position.ticket
                    state.close_command_id = command.command_id
                    state.last_error = None
            elif state.close_command_id is None:
                state.close_command_id = pending_close.command_id

        save_demo_collection_state(state_path, state)
        return state

    selected_trade = _selected_open_paper_trade(overview)
    if selected_trade is None:
        save_demo_collection_state(state_path, state)
        return state
    if selected_trade.trade_id == state.last_completed_trade_id:
        save_demo_collection_state(state_path, state)
        return state
    if read_pending_command(files_dir / COMMAND_FILE) is not None:
        save_demo_collection_state(state_path, state)
        return state
    if read_pending_close_command(files_dir / CLOSE_COMMAND_FILE) is not None:
        save_demo_collection_state(state_path, state)
        return state

    proposal = ExecutionProposal(
        id=f"demo-collection-{selected_trade.trade_id}",
        symbol=selected_trade.symbol,
        timeframe=Timeframe.M5,
        side=selected_trade.side,
        strategy_id=overview.portfolio.selected_strategy_id or "",
        at=selected_trade.signal_at,
        reason="automatic isolated broker DEMO collection",
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
        state.paper_trade_id = selected_trade.trade_id
        state.strategy_id = proposal.strategy_id
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
        return DemoCollectionState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DemoCollectionState()


def save_demo_collection_state(path: Path, state: DemoCollectionState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _selected_open_paper_trade(overview: TradingOverview) -> ShadowPaperTrade | None:
    if overview.portfolio.action not in {
        PortfolioAction.DEMO_COLLECTION,
        PortfolioAction.DEMO_ELIGIBLE,
    }:
        return None
    selected = overview.portfolio.selected_strategy_id
    if selected is None:
        return None
    for row in overview.paper_strategies:
        if row.strategy_id == selected:
            return row.summary.open_trade
    return None


def _find_open_paper_trade(
    overview: TradingOverview,
    trade_id: str | None,
) -> ShadowPaperTrade | None:
    if trade_id is None:
        return None
    for row in overview.paper_strategies:
        trade = row.summary.open_trade
        if trade is not None and trade.trade_id == trade_id:
            return trade
    return None


def _find_closed_paper_trade(runtime_dir: Path, trade_id: str) -> ShadowPaperTrade | None:
    for path in sorted(runtime_dir.glob("*_paper_trades.jsonl")):
        for trade in load_closed_trades(path):
            if trade.trade_id == trade_id:
                return trade
    return None


def _bridge_position_for_state(positions, state: DemoCollectionState):
    if state.ticket is not None:
        for position in positions:
            if position.ticket == state.ticket:
                return position
    if len(positions) == 1:
        return positions[0]
    return None


def _complete_state(
    state: DemoCollectionState,
    *,
    error: str | None = None,
) -> DemoCollectionState:
    return DemoCollectionState(
        last_completed_trade_id=state.paper_trade_id,
        last_error=error,
    )
