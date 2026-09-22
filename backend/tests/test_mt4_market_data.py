import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.market import Timeframe
from app.services.mt4_market_data import load_closed_market_bars

TZ = ZoneInfo("Europe/Athens")


def test_runtime_market_data_prefers_fresher_legacy_csv_over_stale_snapshot(
    tmp_path: Path,
) -> None:
    (tmp_path / "mt4_bars_BTCUSD_M5.json").write_text(
        json.dumps(
            {
                "symbol": "BTCUSD",
                "timeframe": "M5",
                "first_shift": "1",
                "bars": {
                    "0": {
                        "timestamp": "1789821000",
                        "open": "81397.92",
                        "high": "81425.61",
                        "low": "81249.73",
                        "close": "81295.77",
                        "volume": "1931",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "BTCUSD-M5.csv").write_text(
        "20260919,12:35:00,81295.71,81305.66,81246.84,81300.10,1931\n"
        "20260919,12:40:00,81300.10,81340.00,81280.00,81330.00,2000\n",
        encoding="utf-8",
    )
    (tmp_path / "mt4_research_bars_BTCUSD_M5.csv").write_text(
        "timestamp,open,high,low,close,volume\n"
        "1789820700,81380,81400,81350,81390,1800\n",
        encoding="utf-8",
    )

    bars = load_closed_market_bars(
        tmp_path,
        "BTCUSD",
        Timeframe.M5,
        datetime(2026, 9, 19, 12, 46, tzinfo=TZ),
    )

    assert bars
    assert bars[-1].timestamp.isoformat() == "2026-09-19T12:40:00+03:00"
    assert bars[-1].close == 81330.0


def test_runtime_market_data_filters_open_bar_before_source_selection(
    tmp_path: Path,
) -> None:
    (tmp_path / "mt4_bars_BTCUSD_M5.json").write_text(
        json.dumps(
            {
                "symbol": "BTCUSD",
                "timeframe": "M5",
                "first_shift": "1",
                "bars": {
                    "0": {
                        "timestamp": "1789821300",
                        "open": "81295.71",
                        "high": "81305.66",
                        "low": "81246.84",
                        "close": "81300.10",
                        "volume": "1931",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "BTCUSD-M5.csv").write_text(
        "20260919,12:40:00,81300.10,81340.00,81280.00,81330.00,2000\n"
        "20260919,12:45:00,81330.00,81360.00,81320.00,81350.00,2100\n",
        encoding="utf-8",
    )

    bars = load_closed_market_bars(
        tmp_path,
        "BTCUSD",
        Timeframe.M5,
        datetime(2026, 9, 19, 12, 46, tzinfo=TZ),
    )

    assert bars[-1].timestamp.isoformat() == "2026-09-19T12:40:00+03:00"
