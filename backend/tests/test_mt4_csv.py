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
    assert bars[0].timestamp.isoformat() == "2026-09-18T10:00:00+03:00"
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
    assert summary["first_bar"].isoformat() == "2026-09-18T10:00:00+03:00"
    assert summary["last_bar"].isoformat() == "2026-09-18T10:15:00+03:00"


def test_reader_handles_closed_bar_epoch_research_export(tmp_path: Path) -> None:
    path = tmp_path / "mt4_research_bars_XAUUSD_M5.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "1789718400,4300,4301,4299,4300.5,100\n"
        "1789718700,4300.5,4302,4300,4301.5,120\n",
        encoding="utf-8",
    )

    bars = read_mt4_csv(path, "XAUUSD", Timeframe.M5)

    assert len(bars) == 2
    assert bars[0].timestamp.tzinfo is not None
    assert bars[1].timestamp > bars[0].timestamp
    assert bars[1].close == 4301.5
