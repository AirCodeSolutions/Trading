from pathlib import Path

from app.domain.market import Timeframe
from app.services.mt4_csv import read_mt4_csv, summarize_mt4_csv


def test_reader_handles_header_reverse_order_and_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "EURUSD-M5.csv"
    path.write_text(
        "Date,Timestamp,Open,High,Low,Close,Volume\n"
        "20260918,10:05:00,1.1,1.2,1.0,1.15,10\n"
        "20260918,10:00:00,1.0,1.1,0.9,1.05,9\n"
        "20260918,10:05:00,1.1,1.2,1.0,1.16,11\n",
        encoding="utf-8",
    )

    bars = read_mt4_csv(path, "EURUSD", Timeframe.M5)

    assert len(bars) == 2
    assert bars[0].timestamp.isoformat() == "2026-09-18T10:00:00"
    assert bars[1].close == 1.16


def test_reader_handles_mt4_file_without_header(tmp_path: Path) -> None:
    path = tmp_path / "BTCUSD-M15.csv"
    path.write_text(
        "20260918,10:00:00,80000,80100,79900,80050,100\n"
        "20260918,10:15:00,80050,80200,80000,80150,120\n",
        encoding="utf-8",
    )

    summary = summarize_mt4_csv(path, "BTCUSD", Timeframe.M15)

    assert summary["count"] == 2
    assert summary["first_bar"].isoformat() == "2026-09-18T10:00:00"
    assert summary["last_bar"].isoformat() == "2026-09-18T10:15:00"
