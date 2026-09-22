from __future__ import annotations

from pathlib import Path
from statistics import fmean
from uuid import uuid4

from app.domain.demo_execution import (
    DemoBridgeCommandStatus,
    DemoBridgeResult,
    DemoCloseCommand,
    DemoOrderCommand,
)
from app.domain.execution_audit import (
    ExecutionAuditEvent,
    ExecutionAuditEventType,
    ExecutionQualitySample,
    ExecutionQualitySummary,
)
from app.domain.trading import Side

AUDIT_FILE = "demo_execution_audit.jsonl"


def append_open_command_event(
    path: Path,
    command: DemoOrderCommand,
    *,
    reference_entry_price: float,
) -> ExecutionAuditEvent:
    event = ExecutionAuditEvent(
        event_id=uuid4().hex,
        event_type=ExecutionAuditEventType.OPEN_COMMAND,
        at=command.issued_at,
        command_id=command.command_id,
        symbol=command.symbol,
        strategy_id=command.strategy_id,
        side=command.side,
        lots=command.lots,
        reference_entry_price=reference_entry_price,
        stop_loss=command.stop_loss,
        take_profit=command.take_profit,
    )
    append_execution_audit_event(path, event)
    return event


def append_close_command_event(
    path: Path,
    command: DemoCloseCommand,
) -> ExecutionAuditEvent:
    event = ExecutionAuditEvent(
        event_id=uuid4().hex,
        event_type=ExecutionAuditEventType.CLOSE_COMMAND,
        at=command.issued_at,
        command_id=command.command_id,
        symbol=command.symbol,
        strategy_id=command.strategy_id,
        ticket=command.ticket,
    )
    append_execution_audit_event(path, event)
    return event


def append_bridge_result_if_new(
    path: Path,
    result: DemoBridgeResult | None,
    *,
    at,
) -> ExecutionAuditEvent | None:
    if result is None:
        return None
    events = load_execution_audit_events(path)
    if any(
        event.event_type == ExecutionAuditEventType.BRIDGE_RESULT
        and event.command_id == result.command_id
        for event in events
    ):
        return None

    command = next(
        (
            event
            for event in reversed(events)
            if event.command_id == result.command_id
            and event.event_type
            in {
                ExecutionAuditEventType.OPEN_COMMAND,
                ExecutionAuditEventType.CLOSE_COMMAND,
            }
        ),
        None,
    )
    event = ExecutionAuditEvent(
        event_id=uuid4().hex,
        event_type=ExecutionAuditEventType.BRIDGE_RESULT,
        at=at,
        command_id=result.command_id,
        symbol=command.symbol if command is not None else None,
        strategy_id=command.strategy_id if command is not None else None,
        side=command.side if command is not None else None,
        lots=command.lots if command is not None else None,
        reference_entry_price=(
            command.reference_entry_price if command is not None else None
        ),
        stop_loss=command.stop_loss if command is not None else None,
        take_profit=command.take_profit if command is not None else None,
        ticket=result.ticket,
        status=result.status,
        error_code=result.error_code,
        fill_price=result.fill_price,
    )
    append_execution_audit_event(path, event)
    return event


def append_execution_audit_event(path: Path, event: ExecutionAuditEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json())
        handle.write("\n")


def load_execution_audit_events(path: Path) -> list[ExecutionAuditEvent]:
    if not path.is_file():
        return []
    rows: list[ExecutionAuditEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(ExecutionAuditEvent.model_validate_json(line))
            except ValueError:
                continue
    return rows


def build_execution_quality_summary(path: Path) -> ExecutionQualitySummary:
    events = load_execution_audit_events(path)
    commands = [
        event
        for event in events
        if event.event_type
        in {
            ExecutionAuditEventType.OPEN_COMMAND,
            ExecutionAuditEventType.CLOSE_COMMAND,
        }
    ]
    results = [
        event
        for event in events
        if event.event_type == ExecutionAuditEventType.BRIDGE_RESULT
    ]
    commands_by_id = {event.command_id: event for event in commands}
    samples: list[ExecutionQualitySample] = []
    unpaired = 0
    for result in results:
        if result.status != DemoBridgeCommandStatus.FILLED:
            continue
        command = commands_by_id.get(result.command_id)
        if command is None:
            unpaired += 1
            continue
        if command.event_type == ExecutionAuditEventType.CLOSE_COMMAND:
            continue
        if (
            command.symbol is None
            or command.strategy_id is None
            or command.side is None
            or command.lots is None
            or command.reference_entry_price is None
            or command.stop_loss is None
            or result.fill_price <= 0
            or result.ticket <= 0
        ):
            unpaired += 1
            continue

        slippage = (
            result.fill_price - command.reference_entry_price
            if command.side == Side.BUY
            else command.reference_entry_price - result.fill_price
        )
        adverse = max(0.0, slippage)
        risk_distance = abs(command.reference_entry_price - command.stop_loss)
        slippage_r = slippage / risk_distance if risk_distance > 0 else 0.0
        samples.append(
            ExecutionQualitySample(
                command_id=command.command_id,
                at=result.at,
                symbol=command.symbol,
                strategy_id=command.strategy_id,
                side=command.side,
                lots=command.lots,
                reference_entry_price=command.reference_entry_price,
                fill_price=result.fill_price,
                slippage_price=slippage,
                adverse_slippage_price=adverse,
                slippage_r=slippage_r,
                ticket=result.ticket,
            )
        )

    adverse_values = [sample.adverse_slippage_price for sample in samples]
    return ExecutionQualitySummary(
        commands=len(commands),
        fills=sum(
            result.status == DemoBridgeCommandStatus.FILLED for result in results
        ),
        refused=sum(
            result.status == DemoBridgeCommandStatus.REFUSED for result in results
        ),
        errors=sum(
            result.status == DemoBridgeCommandStatus.ERROR for result in results
        ),
        unpaired_results=unpaired,
        average_adverse_slippage_price=(
            fmean(adverse_values) if adverse_values else 0.0
        ),
        max_adverse_slippage_price=max(adverse_values) if adverse_values else 0.0,
        average_slippage_r=(
            fmean(sample.slippage_r for sample in samples) if samples else 0.0
        ),
        samples=samples[-50:][::-1],
    )
