import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.macro import MacroEvent, MacroImpact
from app.services.macro_gate import (
    active_macro_blackouts,
    classify_macro_signal_context,
    macro_gate_status,
)

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



def test_shared_blackout_logic_compares_timezone_aware_instants() -> None:
    event = MacroEvent(
        event_id="nfp",
        name="NFP",
        start_at=datetime(2026, 7, 2, 8, 30, tzinfo=ZoneInfo("America/New_York")),
        end_at=datetime(2026, 7, 2, 8, 30, tzinfo=ZoneInfo("America/New_York")),
        impact=MacroImpact.HIGH,
        currencies=["USD"],
        pre_block_minutes=30,
        post_block_minutes=45,
        source="test",
    )
    athens = ZoneInfo("Europe/Athens")

    active = active_macro_blackouts(
        [event],
        datetime(2026, 7, 2, 15, 15, tzinfo=athens),
    )

    assert [item.event_id for item in active] == ["nfp"]


def test_macro_signal_context_marks_blackout_post_safe_and_normal() -> None:
    event = MacroEvent(
        event_id="nfp",
        name="NFP",
        start_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        end_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        impact=MacroImpact.HIGH,
        currencies=["USD"],
        pre_block_minutes=30,
        post_block_minutes=45,
        source="test",
    )

    blackout = classify_macro_signal_context(
        [event],
        datetime(2026, 10, 2, 9, 0, tzinfo=TZ),
    )
    assert blackout.phase == "blackout"
    assert blackout.event_id == "nfp"
    assert blackout.safe_resume_at == datetime(2026, 10, 2, 9, 15, tzinfo=TZ)
    assert blackout.minutes_from_safe_resume == -15.0

    post_safe = classify_macro_signal_context(
        [event],
        datetime(2026, 10, 2, 10, 0, tzinfo=TZ),
    )
    assert post_safe.phase == "post_safe"
    assert post_safe.event_name == "NFP"
    assert post_safe.minutes_from_safe_resume == 45.0

    normal = classify_macro_signal_context(
        [event],
        datetime(2026, 10, 2, 12, 0, tzinfo=TZ),
    )
    assert normal.phase == "normal"
    assert normal.event_id is None
    assert normal.minutes_from_safe_resume is None


def test_macro_signal_context_ignores_other_currency_and_medium_impact() -> None:
    medium_usd = MacroEvent(
        event_id="medium",
        name="Medium USD",
        start_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        end_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        impact=MacroImpact.MEDIUM,
        currencies=["USD"],
        source="test",
    )
    high_eur = MacroEvent(
        event_id="eur",
        name="High EUR",
        start_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        end_at=datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
        impact=MacroImpact.HIGH,
        currencies=["EUR"],
        source="test",
    )

    context = classify_macro_signal_context(
        [medium_usd, high_eur],
        datetime(2026, 10, 2, 8, 30, tzinfo=TZ),
    )

    assert context.phase == "normal"
