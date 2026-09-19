import json
from pathlib import Path

import pytest

from app.domain.market import Timeframe
from app.services.mt4_live_bars import read_closed_bar_snapshot


def test_live_snapshot_preserves_server_wall_clock(tmp_path: Path) -> None:
    path = tmp_path / "mt4_bars_BTCUSD_M5.json"
    payload = {
        "generated_at": "1789822532",
        "symbol": "BTCUSD",
        "timeframe": "M5",
        "first_shift": "1",
        "count": "2",
        "bars": {
            "0": {
                "timestamp": "1789821000",
                "open": "81397.92",
                "high": "81425.61",
                "low": "81249.73",
                "close": "81295.77",
                "volume": "1931",
            },
            "1": {
                "timestamp": "1789821300",
                "open": "81295.71",
                "high": "81305.66",
                "low": "81246.84",
                "close": "81300.10",
                "volume": "1931",
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    bars = read_closed_bar_snapshot(path, "BTCUSD", Timeframe.M5)

    assert len(bars) == 2
    assert bars[0].timestamp.isoformat() == "2026-09-19T12:30:00+03:00"
    assert bars[1].timestamp.isoformat() == "2026-09-19T12:35:00+03:00"


def test_live_snapshot_refuses_open_bar_payload(tmp_path: Path) -> None:
    path = tmp_path / "mt4_bars_BTCUSD_M5.json"
    path.write_text(
        json.dumps(
            {
                "symbol": "BTCUSD",
                "timeframe": "M5",
                "first_shift": "0",
                "bars": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="closed bars only"):
        read_closed_bar_snapshot(path, "BTCUSD", Timeframe.M5)
