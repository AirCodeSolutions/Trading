import json
from datetime import date
from pathlib import Path

from app.services.broker_history import summarize_trading_new_closed_tickets


def write_audit(path: Path, *, ticket: int = 123, command_id: str = "close-1") -> None:
    rows = [
        {
            "event_id": "a",
            "event_type": "close_command",
            "at": "2026-09-23T10:35:20+03:00",
            "command_id": command_id,
            "ticket": ticket,
        },
        {
            "event_id": "b",
            "event_type": "bridge_result",
            "at": "2026-09-23T10:36:00+03:00",
            "command_id": command_id,
            "ticket": ticket,
            "status": "filled",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_history(
    path: Path,
    *,
    ticket: int = 123,
    magic: int = 560619,
    profit: float = 2.64,
) -> None:
    payload = {
        "timestamp": "1790180660",
        "symbol": "BTCUSD",
        "history": {
            str(ticket): {
                "ticket": str(ticket),
                "symbol": "BTCUSD",
                "type": "SELL",
                "lots": "0.02000000",
                "openPrice": "86385.37000000",
                "closePrice": "86234.48000000",
                "stopLoss": "86581.29000000",
                "takeProfit": "86214.71000000",
                "profit": str(profit),
                "openTime": "1790155870",
                "closeTime": "1790159754",
                "magic": str(magic),
                "comment": "",
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_broker_history_reconciles_closed_trading_new_ticket(tmp_path: Path) -> None:
    audit = tmp_path / "demo_execution_audit.jsonl"
    write_audit(audit)
    write_history(tmp_path / "mt4_history_BTCUSD.json")

    summary = summarize_trading_new_closed_tickets(
        tmp_path,
        audit,
        magic_number=560619,
        report_date=date(2026, 9, 23),
    )

    assert summary.complete is True
    assert summary.trades == 1
    assert summary.realized_pnl_eur == 2.64
    assert summary.missing_tickets == []
    assert summary.closed_trades[0].ticket == 123


def test_broker_history_marks_missing_closed_ticket_incomplete(tmp_path: Path) -> None:
    audit = tmp_path / "demo_execution_audit.jsonl"
    write_audit(audit, ticket=456)

    summary = summarize_trading_new_closed_tickets(
        tmp_path,
        audit,
        magic_number=560619,
        report_date=date(2026, 9, 23),
    )

    assert summary.complete is False
    assert summary.trades == 1
    assert summary.realized_pnl_eur == 0
    assert summary.missing_tickets == [456]


def test_broker_history_ignores_other_magic_number(tmp_path: Path) -> None:
    audit = tmp_path / "demo_execution_audit.jsonl"
    write_audit(audit)
    write_history(tmp_path / "mt4_history_BTCUSD.json", magic=51051)

    summary = summarize_trading_new_closed_tickets(
        tmp_path,
        audit,
        magic_number=560619,
        report_date=date(2026, 9, 23),
    )

    assert summary.complete is False
    assert summary.missing_tickets == [123]
