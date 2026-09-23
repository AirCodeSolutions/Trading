import json
from datetime import UTC, date, datetime
from pathlib import Path

from app.domain.broker_history import BrokerClosedSummary, BrokerClosedTrade
from app.domain.trading import Side


def summarize_trading_new_closed_tickets(
    files_dir: Path,
    audit_path: Path,
    *,
    magic_number: int,
    report_date: date,
) -> BrokerClosedSummary:
    ticket_ids = _closed_tickets_from_audit(audit_path, report_date)
    if not ticket_ids:
        return BrokerClosedSummary(trades=0, realized_pnl_eur=0.0)

    history = _load_all_history(files_dir)
    matched = [
        trade
        for ticket in sorted(ticket_ids)
        if (trade := history.get(ticket)) is not None
        and trade.magic_number == magic_number
    ]
    found_tickets = {trade.ticket for trade in matched}
    missing = sorted(ticket_ids - found_tickets)
    return BrokerClosedSummary(
        trades=len(ticket_ids),
        realized_pnl_eur=sum(trade.profit_eur for trade in matched),
        complete=not missing,
        missing_tickets=missing,
        closed_trades=matched,
    )


def _closed_tickets_from_audit(path: Path, report_date: date) -> set[int]:
    if not path.is_file():
        return set()
    close_commands: dict[str, int] = {}
    closed_tickets: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        command_id = str(payload.get("command_id", ""))
        event_type = payload.get("event_type")
        if event_type == "close_command":
            try:
                ticket = int(payload.get("ticket", 0) or 0)
            except (TypeError, ValueError):
                ticket = 0
            if command_id and ticket > 0:
                close_commands[command_id] = ticket
            continue
        if event_type != "bridge_result" or command_id not in close_commands:
            continue
        if str(payload.get("status", "")).lower() != "filled":
            continue
        at = _parse_iso_datetime(payload.get("at"))
        if at is None or at.date() != report_date:
            continue
        closed_tickets.add(close_commands[command_id])
    return closed_tickets


def _load_all_history(files_dir: Path) -> dict[int, BrokerClosedTrade]:
    result: dict[int, BrokerClosedTrade] = {}
    for path in sorted(files_dir.glob("mt4_history_*.json")):
        for trade in _load_history_file(path):
            result[trade.ticket] = trade
    return result


def _load_history_file(path: Path) -> list[BrokerClosedTrade]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    history = payload.get("history") if isinstance(payload, dict) else None
    if not isinstance(history, dict):
        return []

    result: list[BrokerClosedTrade] = []
    for value in history.values():
        if not isinstance(value, dict):
            continue
        try:
            side_raw = str(value["type"]).upper()
            if side_raw not in {"BUY", "SELL"}:
                continue
            close_time = int(value["closeTime"])
            if close_time <= 0:
                continue
            result.append(
                BrokerClosedTrade(
                    ticket=int(value["ticket"]),
                    symbol=str(value["symbol"]).upper(),
                    side=Side.BUY if side_raw == "BUY" else Side.SELL,
                    lots=float(value["lots"]),
                    open_price=float(value["openPrice"]),
                    close_price=float(value["closePrice"]),
                    stop_loss=float(value.get("stopLoss", 0) or 0),
                    take_profit=float(value.get("takeProfit", 0) or 0),
                    profit_eur=float(value.get("profit", 0) or 0),
                    open_at=_mt4_wall_timestamp(int(value["openTime"])),
                    close_at=_mt4_wall_timestamp(close_time),
                    magic_number=int(value.get("magic", 0) or 0),
                    comment=str(value.get("comment", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _mt4_wall_timestamp(value: int) -> datetime:
    # MT4 exporter serializes server-wall seconds. UTC preserves the same
    # displayed wall-clock date/time without applying the host timezone offset.
    return datetime.fromtimestamp(value, UTC)


def _parse_iso_datetime(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
