from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.macro import MacroEvent, MacroImpact
from app.services.macro_sync import _merge_events

NY = ZoneInfo("America/New_York")


def event(
    event_id: str,
    name: str,
    at: datetime,
    *,
    source: str,
) -> MacroEvent:
    return MacroEvent(
        event_id=event_id,
        name=name,
        start_at=at,
        end_at=at,
        impact=MacroImpact.HIGH,
        currencies=["USD"],
        pre_block_minutes=30,
        post_block_minutes=45,
        source=source,
    )


def test_macro_sync_prefers_versioned_base_release_over_same_bls_event() -> None:
    at = datetime(2026, 9, 4, 8, 30, tzinfo=NY)
    base = event(
        "bls-nfp-2026-09-04",
        "US Employment Situation (NFP)",
        at,
        source="BLS release calendar",
    )
    synced = event(
        "bls-sync-2026-09-04-employment-situation-for-august-2026",
        "Employment Situation for August 2026",
        at,
        source="BLS official ICS calendar",
    )

    merged = _merge_events([base], [synced])

    assert len(merged) == 1
    assert merged[0].event_id == base.event_id


def test_macro_sync_keeps_distinct_release_families_at_same_time() -> None:
    at = datetime(2026, 9, 10, 8, 30, tzinfo=NY)
    cpi = event(
        "bls-cpi-example",
        "US Consumer Price Index",
        at,
        source="base",
    )
    nfp = event(
        "bls-sync-example-employment",
        "Employment Situation for August 2026",
        at,
        source="sync",
    )

    merged = _merge_events([cpi], [nfp])

    assert {item.event_id for item in merged} == {
        "bls-cpi-example",
        "bls-sync-example-employment",
    }
