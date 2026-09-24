import csv
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import ExecutionMode, settings
from app.domain.admission import AdmissionState
from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.demo_execution import (
    DemoBridgeCommandStatus,
    DemoBridgePosition,
    DemoBridgeResult,
    DemoCloseCommand,
    DemoExecutionGuard,
    DemoExecutionStatus,
    DemoOrderCommand,
)
from app.domain.macro import MacroGateStatus
from app.domain.portfolio import PortfolioAction, TradingOverview
from app.domain.trading import Side
from app.services.execution_audit import (
    append_close_command_event,
    append_open_command_event,
)

COMMAND_FILE = "trading_demo_command.csv"
CLOSE_COMMAND_FILE = "trading_demo_close_command.csv"
RESULT_FILE = "trading_demo_result.csv"
POSITIONS_FILE = "trading_demo_positions.csv"


def build_demo_guard(
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
    *,
    bridge_positions: list[DemoBridgePosition] | None = None,
    drain_enabled: bool = False,
    target_symbol: str | None = None,
) -> DemoExecutionGuard:
    reasons: list[str] = []
    broker_is_demo = bool(overview.broker and overview.broker.is_demo)
    broker_positions = overview.broker.observed_positions if overview.broker else 0
    bridge_position_count = len(bridge_positions or [])
    remaining_daily_loss = overview.risk.remaining_daily_loss_budget_eur
    qualified_collectors = sum(
        row.historical_state == AdmissionState.SHADOW and row.paper_entry_allowed
        for row in overview.paper_strategies
    )
    transport_armed = (
        settings.execution_mode == ExecutionMode.DEMO
        and settings.demo_execution_bridge_enabled
        and not settings.live_trading_enabled
        and broker_is_demo
    )
    auto_collection_armed = (
        transport_armed
        and settings.demo_collection_enabled
        and not drain_enabled
    )
    waiting_for_qualified_trade = (
        auto_collection_armed
        and overview.portfolio.action == PortfolioAction.NO_TRADE
        and qualified_collectors > 0
    )

    if drain_enabled:
        reasons.append("runtime drain is enabled")
    if settings.execution_mode != ExecutionMode.DEMO:
        reasons.append("execution mode is not demo")
    if not settings.demo_execution_bridge_enabled:
        reasons.append("demo execution bridge is disabled")
    if settings.live_trading_enabled:
        reasons.append("live trading flag must remain disabled for demo execution")
    if not broker_is_demo:
        reasons.append("broker account is not confirmed as demo")
    if overview.portfolio.action not in {
        PortfolioAction.DEMO_COLLECTION,
        PortfolioAction.DEMO_ELIGIBLE,
    }:
        reasons.append("portfolio is not demo eligible")
    if (
        overview.portfolio.action == PortfolioAction.DEMO_COLLECTION
        and not settings.demo_collection_enabled
    ):
        reasons.append("demo collection is disabled")
    normalized_target = target_symbol.upper() if target_symbol else None
    if normalized_target is not None and any(
        position.symbol.upper() == normalized_target
        for position in (bridge_positions or [])
    ):
        reasons.append(
            f"Trading-New bridge already has open position for {normalized_target}"
        )
    if remaining_daily_loss <= 0:
        reasons.append("daily loss budget is exhausted")
    if macro.blocked:
        reasons.append(macro.reason)

    return DemoExecutionGuard(
        at=now,
        ready=not reasons,
        transport_armed=transport_armed,
        auto_collection_armed=auto_collection_armed,
        drain_enabled=drain_enabled,
        waiting_for_qualified_trade=waiting_for_qualified_trade,
        qualified_collectors=qualified_collectors,
        execution_mode=settings.execution_mode.value,
        bridge_enabled=settings.demo_execution_bridge_enabled,
        live_trading_enabled=settings.live_trading_enabled,
        broker_is_demo=broker_is_demo,
        portfolio_action=overview.portfolio.action,
        macro_blocked=macro.blocked,
        broker_observed_positions=broker_positions,
        bridge_open_positions=bridge_position_count,
        remaining_daily_loss_budget_eur=remaining_daily_loss,
        reasons=reasons,
    )


def submit_selected_demo_order(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    proposal: ExecutionProposal,
    now: datetime,
    audit_path: Path | None = None,
) -> DemoOrderCommand:
    bridge_positions = read_demo_positions(files_dir / POSITIONS_FILE)
    guard = build_demo_guard(
        overview,
        macro,
        now,
        bridge_positions=bridge_positions,
        target_symbol=proposal.symbol,
    )
    if not guard.ready:
        raise ValueError("; ".join(guard.reasons))
    if proposal.status != ProposalStatus.AUTHORIZED:
        raise ValueError("execution proposal is not authorized")
    row = next(
        (
            item
            for item in overview.paper_strategies
            if item.strategy_id == proposal.strategy_id
            and item.summary.open_trade is not None
        ),
        None,
    )
    if row is None or row.summary.open_trade is None:
        raise ValueError("proposal strategy has no open paper trade")
    if (
        not row.paper_entry_allowed
        and proposal.strategy_id != overview.portfolio.selected_strategy_id
    ):
        raise ValueError("proposal strategy is not PAPER-entry eligible")

    trade = row.summary.open_trade
    if trade.risk_eur > overview.risk.remaining_daily_loss_budget_eur:
        raise ValueError("trade risk exceeds remaining daily loss budget")
    if proposal.symbol.upper() != trade.symbol.upper():
        raise ValueError("proposal symbol does not match selected paper trade")
    if proposal.side != trade.side:
        raise ValueError("proposal side does not match selected paper trade")

    command_path = files_dir / COMMAND_FILE
    if command_path.is_file():
        pending = read_pending_command(command_path)
        if pending is not None:
            raise ValueError("a demo command is already pending")

    command = DemoOrderCommand(
        command_id=uuid4().hex,
        symbol=trade.symbol,
        side=trade.side,
        lots=trade.lots,
        stop_loss=trade.stop_price,
        take_profit=trade.target_price,
        strategy_id=proposal.strategy_id,
        issued_at=now,
        magic_number=settings.demo_magic_number,
        slippage_points=settings.demo_max_slippage_points,
        proposal_status=proposal.status,
    )
    _write_command(command_path, command)
    if audit_path is not None:
        try:
            append_open_command_event(
                audit_path,
                command,
                reference_entry_price=trade.entry_price,
                reference_risk_eur=trade.risk_eur,
            )
        except OSError:
            pass
    return command


def build_demo_status(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
    drain_enabled: bool = False,
) -> DemoExecutionStatus:
    bridge_positions = read_demo_positions(files_dir / POSITIONS_FILE)
    return DemoExecutionStatus(
        guard=build_demo_guard(
            overview,
            macro,
            now,
            bridge_positions=bridge_positions,
            drain_enabled=drain_enabled,
        ),
        pending_command=read_pending_command(files_dir / COMMAND_FILE),
        pending_close_command=read_pending_close_command(
            files_dir / CLOSE_COMMAND_FILE
        ),
        latest_result=read_demo_result(files_dir / RESULT_FILE),
        bridge_positions=bridge_positions,
    )


def submit_demo_close_order(
    *,
    files_dir: Path,
    overview: TradingOverview,
    ticket: int,
    strategy_id: str,
    now: datetime,
    audit_path: Path | None = None,
) -> DemoCloseCommand:
    if settings.live_trading_enabled:
        raise ValueError("live trading flag must remain disabled for demo execution")
    if not settings.demo_execution_bridge_enabled:
        raise ValueError("demo execution bridge is disabled")
    if overview.broker is None or not overview.broker.is_demo:
        raise ValueError("broker account is not confirmed as demo")
    if (files_dir / COMMAND_FILE).is_file():
        raise ValueError("a demo open command is still pending")

    positions = read_demo_positions(files_dir / POSITIONS_FILE)
    position = next(
        (position for position in positions if position.ticket == ticket),
        None,
    )
    if position is None:
        raise ValueError("Trading-New bridge ticket is not open")

    close_path = files_dir / CLOSE_COMMAND_FILE
    if close_path.is_file():
        pending = read_pending_close_command(close_path)
        if pending is not None:
            raise ValueError("a demo close command is already pending")

    command = DemoCloseCommand(
        command_id=uuid4().hex,
        ticket=ticket,
        symbol=position.symbol,
        strategy_id=strategy_id,
        issued_at=now,
        magic_number=settings.demo_magic_number,
        slippage_points=settings.demo_max_slippage_points,
    )
    _write_close_command(close_path, command)
    if audit_path is not None:
        try:
            append_close_command_event(audit_path, command)
        except OSError:
            pass
    return command


def read_pending_command(path: Path) -> DemoOrderCommand | None:
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.reader(handle))
        return DemoOrderCommand(
            command_id=row[0],
            symbol=row[1],
            side=row[2].lower(),
            lots=float(row[3]),
            stop_loss=float(row[4]),
            take_profit=float(row[5]),
            strategy_id=row[6],
            issued_at=datetime.fromisoformat(row[7]),
            magic_number=int(row[8]),
            slippage_points=int(row[9]),
            proposal_status=row[10],
        )
    except (IndexError, OSError, StopIteration, TypeError, ValueError):
        return None


def read_pending_close_command(path: Path) -> DemoCloseCommand | None:
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.reader(handle))
        return DemoCloseCommand(
            command_id=row[0],
            ticket=int(row[1]),
            symbol=row[2],
            strategy_id=row[3],
            issued_at=datetime.fromisoformat(row[4]),
            magic_number=int(row[5]),
            slippage_points=int(row[6]),
        )
    except (IndexError, OSError, StopIteration, TypeError, ValueError):
        return None


def read_demo_result(path: Path) -> DemoBridgeResult | None:
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.reader(handle))
        return DemoBridgeResult(
            command_id=row[0],
            status=DemoBridgeCommandStatus(row[1].lower()),
            ticket=int(row[2]),
            error_code=int(row[3]),
            fill_price=float(row[4]),
            stop_loss=float(row[5]),
            take_profit=float(row[6]),
            processed_at=row[7],
        )
    except (IndexError, OSError, StopIteration, TypeError, ValueError):
        return None


def read_demo_positions(path: Path) -> list[DemoBridgePosition]:
    if not path.is_file():
        return []
    positions: list[DemoBridgePosition] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                side = Side.BUY if row["side"].upper() == "BUY" else Side.SELL
                positions.append(
                    DemoBridgePosition(
                        ticket=int(row["ticket"]),
                        symbol=row["symbol"],
                        side=side,
                        lots=float(row["lots"]),
                        open_price=float(row["open_price"]),
                        stop_loss=float(row["stop_loss"]),
                        take_profit=float(row["take_profit"]),
                        profit=float(row["profit"]),
                        open_time=row["open_time"],
                        strategy_comment=row.get("comment", ""),
                    )
                )
    except (KeyError, OSError, TypeError, ValueError):
        return []
    return positions


def _write_command(path: Path, command: DemoOrderCommand) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                command.command_id,
                command.symbol,
                command.side.value.upper(),
                f"{command.lots:.8f}",
                f"{command.stop_loss:.8f}",
                f"{command.take_profit:.8f}",
                command.strategy_id,
                command.issued_at.isoformat(),
                command.magic_number,
                command.slippage_points,
                command.proposal_status.value,
            ]
        )
    temporary.replace(path)


def _write_close_command(path: Path, command: DemoCloseCommand) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                command.command_id,
                command.ticket,
                command.symbol,
                command.strategy_id,
                command.issued_at.isoformat(),
                command.magic_number,
                command.slippage_points,
            ]
        )
    temporary.replace(path)
