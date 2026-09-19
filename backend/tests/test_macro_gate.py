import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.macro_gate import macro_gate_status

TZ = ZoneInfo("America/New_York")


def test_high_impact_event_blocks_inside_configured_window(tmp_path: Path) -> None:
    path = tmp_path / "macro.json"
    path.write_text(
        json.dumps(
            [
                {
                    "event_id": "nfp",
                    "name": "NFP",
                    "start_at": "2026-10-02T08:30:00-04:00",
                    "end_at": "2026-10-02T08:30:00-04:00",
                    "impact": "high",
                    "currencies": ["USD"],
                    "pre_block_minutes": 30,
                    "post_block_minutes": 45,
                    "source": "test",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = macro_gate_status(
        path,
        datetime(2026, 10, 2, 8, 15, tzinfo=TZ),
    )

    assert result.blocked is True
    assert result.active_events[0].event_id == "nfp"


def test_macro_gate_reports_next_event_without_blocking(tmp_path: Path) -> None:
    path = tmp_path / "macro.json"
    path.write_text(
        json.dumps(
            [
                {
                    "event_id": "cpi",
                    "name": "CPI",
                    "start_at": "2026-10-14T08:30:00-04:00",
                    "end_at": "2026-10-14T08:30:00-04:00",
                    "impact": "high",
                    "currencies": ["USD"],
                    "source": "test",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = macro_gate_status(
        path,
        datetime(2026, 10, 1, 12, 0, tzinfo=TZ),
    )

    assert result.blocked is False
    assert result.next_event is not None
    assert result.next_event.event_id == "cpi"
