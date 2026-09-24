import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.services.xau_microbar import (
    LEDGER_FILE,
    STATE_FILE,
    load_xau_microbar_summary,
    sample_xau_microbar_once,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 24, 10, 0, 0, tzinfo=TZ)


def server_epoch(at: datetime) -> int:
    wall_clock_utc = at.replace(tzinfo=UTC)
    return int(wall_clock_utc.timestamp())


def write_quote(
    files_dir: Path,
    at: datetime,
    *,
    bid: float,
    ask: float,
) -> None:
    path = files_dir / "trading_demo_spec_XAUUSD.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "symbol",
                "bid",
                "ask",
                "digits",
                "contract_size",
                "tick_size",
                "tick_value",
                "point",
                "min_lot",
                "max_lot",
                "lot_step",
                "stop_level",
                "margin_required",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": server_epoch(at),
                "symbol": "XAUUSD",
                "bid": bid,
                "ask": ask,
                "digits": 2,
                "contract_size": 100,
                "tick_size": 0.01,
                "tick_value": 1,
                "point": 0.01,
                "min_lot": 0.01,
                "max_lot": 10000,
                "lot_step": 0.01,
                "stop_level": 0,
                "margin_required": 376,
            }
        )


def test_microbar_aggregates_quotes_and_closes_on_next_minute(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    write_quote(
        files_dir,
        START + timedelta(seconds=1),
        bid=4280.00,
        ask=4280.28,
    )
    first = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
    )
    assert first.closed_bars == 0
    assert first.total_quote_samples == 1
    assert first.current_bar is not None
    assert first.current_bar.mid_open == pytest.approx(4280.14)

    write_quote(
        files_dir,
        START + timedelta(seconds=20),
        bid=4279.50,
        ask=4279.80,
    )
    second = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=21),
    )
    assert second.total_quote_samples == 2
    assert second.current_bar is not None
    assert second.current_bar.bid_low == 4279.50
    assert second.current_bar.ask_low == 4279.80
    assert second.current_bar.quote_count == 2

    write_quote(
        files_dir,
        START + timedelta(minutes=1, seconds=2),
        bid=4281.00,
        ask=4281.26,
    )
    third = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(minutes=1, seconds=3),
    )

    assert third.closed_bars == 1
    assert third.total_quote_samples == 3
    assert third.latest_closed_bar_at == START
    assert third.recent[0].mid_close == pytest.approx(4279.65)
    assert third.recent[0].quote_count == 2
    assert third.current_bar is not None
    assert third.current_bar.minute_at == START + timedelta(minutes=1)
    assert (runtime_dir / LEDGER_FILE).read_text().count("\n") == 1


def test_microbar_deduplicates_same_broker_timestamp(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    at = START + timedelta(seconds=4)
    write_quote(files_dir, at, bid=4280.0, ask=4280.28)

    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=5),
    )
    repeated = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=6),
    )

    assert repeated.total_quote_samples == 1
    assert repeated.current_bar is not None
    assert repeated.current_bar.quote_count == 1


def test_microbar_rejects_stale_startup_quote_without_backfill(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START - timedelta(minutes=5),
        bid=4280.0,
        ask=4280.28,
    )

    summary = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START,
    )

    assert summary.started_at == START
    assert summary.total_quote_samples == 0
    assert summary.closed_bars == 0
    assert summary.current_bar is None
    assert not (runtime_dir / LEDGER_FILE).exists()
    assert (runtime_dir / STATE_FILE).exists()


def test_microbar_does_not_synthesize_gap_minutes(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START + timedelta(seconds=1),
        bid=4280.0,
        ask=4280.28,
    )
    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
    )

    write_quote(
        files_dir,
        START + timedelta(minutes=4, seconds=1),
        bid=4285.0,
        ask=4285.28,
    )
    summary = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(minutes=4, seconds=2),
    )

    assert summary.closed_bars == 1
    assert summary.recent[0].minute_at == START
    assert summary.current_bar is not None
    assert summary.current_bar.minute_at == START + timedelta(minutes=4)


def test_microbar_summary_marks_live_quote_healthy(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START + timedelta(seconds=2),
        bid=4280.0,
        ask=4280.28,
    )
    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=3),
    )

    summary = load_xau_microbar_summary(
        runtime_dir,
        now=START + timedelta(seconds=10),
    )

    assert summary.healthy is True
    assert summary.quote_age_seconds == 8.0
