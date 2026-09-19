import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.execution_cost_history import (
    collect_execution_cost_snapshot,
    summarize_execution_costs,
)

TZ = ZoneInfo("Europe/Athens")


def test_cost_history_collects_and_summarizes_sanitized_quote(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    files_dir.mkdir()
    ledger = tmp_path / "runtime" / "costs.jsonl"
    (files_dir / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "timestamp": "1789838948",
                "symbol": "BTCUSD",
                "bid": "81522.07",
                "ask": "81546.57",
                "digits": "2",
            }
        ),
        encoding="utf-8",
    )

    appended = collect_execution_cost_snapshot(
        files_dir,
        ledger,
        datetime(2026, 9, 19, 17, 30, tzinfo=TZ),
    )
    summary = summarize_execution_costs(ledger)

    assert appended == 1
    assert summary["BTCUSD"]["samples"] == 1
    assert summary["BTCUSD"]["average_spread"] == 24.5
