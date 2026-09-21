import json
import re
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.domain.macro import MacroEvent, MacroImpact
from app.services.macro_gate import load_macro_events

BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
_HIGH_IMPACT = ("Employment Situation", "Consumer Price Index")
_MEDIUM_IMPACT = ("Producer Price Index",)


def sync_bls_calendar(
    base_path: Path,
    output_path: Path,
    *,
    timeout_seconds: int = 15,
) -> int:
    base_events = [
        event
        for event in load_macro_events(base_path)
        if not event.event_id.startswith("bls-sync-")
    ]
    request = Request(
        BLS_ICS_URL,
        headers={"User-Agent": "TradingResearch/1.0 macro-calendar"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        if not output_path.is_file():
            _write_events(output_path, base_events)
        return 0

    bls_events = parse_bls_ics(text)
    merged = _merge_events(base_events, bls_events)
    _write_events(output_path, merged)
    return len(bls_events)


def parse_bls_ics(text: str) -> list[MacroEvent]:
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    blocks = re.findall(
        r"BEGIN:VEVENT(.*?)END:VEVENT",
        unfolded,
        flags=re.DOTALL,
    )
    events: list[MacroEvent] = []
    for block in blocks:
        summary = _field(block, "SUMMARY")
        dtstart = _dtstart(block)
        if not summary or dtstart is None:
            continue

        impact = _impact(summary)
        if impact is None:
            continue

        slug = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
        events.append(
            MacroEvent(
                event_id=f"bls-sync-{dtstart.date().isoformat()}-{slug[:48]}",
                name=summary,
                start_at=dtstart,
                end_at=dtstart,
                impact=impact,
                currencies=["USD"],
                pre_block_minutes=30,
                post_block_minutes=45 if impact == MacroImpact.HIGH else 30,
                source="BLS official ICS calendar",
            )
        )
    return events


def _impact(summary: str) -> MacroImpact | None:
    if any(name in summary for name in _HIGH_IMPACT):
        return MacroImpact.HIGH
    if any(name in summary for name in _MEDIUM_IMPACT):
        return MacroImpact.MEDIUM
    return None


def _field(block: str, name: str) -> str:
    match = re.search(rf"(?m)^{name}(?:;[^:]*)?:(.+)$", block)
    return match.group(1).strip() if match else ""


def _dtstart(block: str) -> datetime | None:
    match = re.search(
        r"(?m)^DTSTART(?:;TZID=([^:]+))?:(\d{8}T\d{6})$",
        block,
    )
    if match is None:
        return None

    timezone_name = match.group(1) or "America/New_York"
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    try:
        return datetime.strptime(
            match.group(2),
            "%Y%m%dT%H%M%S",
        ).replace(tzinfo=timezone)
    except ValueError:
        return None


def _write_events(path: Path, events: list[MacroEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            [event.model_dump(mode="json") for event in events],
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)



def _merge_events(
    base_events: list[MacroEvent],
    synced_events: list[MacroEvent],
) -> list[MacroEvent]:
    merged = list(base_events)
    seen = {_dedupe_key(event) for event in base_events}
    for event in synced_events:
        key = _dedupe_key(event)
        if key in seen:
            continue
        merged.append(event)
        seen.add(key)
    return sorted(merged, key=lambda event: event.start_at)


def _dedupe_key(event: MacroEvent) -> tuple[object, str]:
    name = event.name.lower()
    event_id = event.event_id.lower()
    if "employment situation" in name or "nfp" in event_id:
        family = "employment_situation"
    elif "consumer price index" in name or "cpi" in event_id:
        family = "consumer_price_index"
    elif "producer price index" in name or "ppi" in event_id:
        family = "producer_price_index"
    else:
        family = event_id
    return event.start_at, family
