import csv
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import ExecutionMode, settings
from app.domain.approval import ExecutionProposal, ProposalStatus
from app.domain.demo_execution import (
    DemoBridgeCommandStatus,
    DemoBridgePosition,
    DemoBridgeResult,
    DemoExecutionGuard,
    DemoExecutionStatus,
    DemoOrderCommand,
)
from app.domain.macro import MacroGateStatus
from app.domain.portfolio import PortfolioAction, TradingOverview
from app.domain.trading import Side

COMMAND_FILE = "trading_demo_command.csv"
RESULT_FILE = "trading_demo_result.csv"
POSITIONS_FILE = "trading_demo_positions.csv"


def build_demo_guard(
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
) -> DemoExecutionGuard:
    reasons: list[str] = []
    broker_is_demo = bool(overview.broker and overview.broker.is_demo)

    if settings.execution_mode != ExecutionMode.DEMO:
        reasons.append("execution mode is not demo")
    if not settings.demo_execution_bridge_enabled:
        reasons.append("demo execution bridge is disabled")
    if settings.live_trading_enabled:
        reasons.append("live trading flag must remain disabled for demo execution")
    if not broker_is_demo:
        reasons.append("broker account is not confirmed as demo")
    if overview.portfolio.action != PortfolioAction.DEMO_ELIGIBLE:
        reasons.append("portfolio is not demo eligible")
    if macro.blocked:
        reasons.append(macro.reason)

    return DemoExecutionGuard(
        at=now,
        ready=not reasons,
        execution_mode=settings.execution_mode.value,
        bridge_enabled=settings.demo_execution_bridge_enabled,
        live_trading_enabled=settings.live_trading_enabled,
        broker_is_demo=broker_is_demo,
        portfolio_action=overview.portfolio.action,
        macro_blocked=macro.blocked,
        reasons=reasons,
    )


def submit_selected_demo_order(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    proposal: ExecutionProposal,
    now: datetime,
) -> DemoOrderCommand:
    guard = build_demo_guard(overview, macro, now)
    if not guard.ready:
        raise ValueError("; ".join(guard.reasons))
    if proposal.status != ProposalStatus.AUTHORIZED:
        raise ValueError("execution proposal is not authorized")
    selected = overview.portfolio.selected_strategy_id
    if selected is None or proposal.strategy_id != selected:
        raise ValueError("proposal does not match selected portfolio strategy")

    row = next(
        (
            item
            for item in overview.paper_strategies
            if item.strategy_id == selected and item.summary.open_trade is not None
        ),
        None,
    )
    if row is None or row.summary.open_trade is None:
        raise ValueError("selected strategy has no open paper trade")

    trade = row.summary.open_trade
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
        strategy_id=selected,
        issued_at=now,
        magic_number=settings.demo_magic_number,
        slippage_points=settings.demo_max_slippage_points,
        proposal_status=proposal.status,
    )
    _write_command(command_path, command)
    return command


def build_demo_status(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    now: datetime,
) -> DemoExecutionStatus:
    return DemoExecutionStatus(
        guard=build_demo_guard(overview, macro, now),
        pending_command=read_pending_command(files_dir / COMMAND_FILE),
        latest_result=read_demo_result(files_dir / RESULT_FILE),
        bridge_positions=read_demo_positions(files_dir / POSITIONS_FILE),
    )


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
