import json
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.macro import (
    MacroEvent,
    MacroGateStatus,
    MacroImpact,
    MacroSignalContext,
    MacroSignalPhase,
)


def load_macro_events(path: Path) -> list[MacroEvent]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []

    events: list[MacroEvent] = []
    for item in payload:
        try:
            event = MacroEvent.model_validate(item)
        except (TypeError, ValueError):
            continue
        if event.end_at < event.start_at:
            continue
        events.append(event)
    return sorted(events, key=lambda item: item.start_at)


def active_macro_blackouts(
    events: list[MacroEvent],
    now: datetime,
    *,
    currency: str = "USD",
) -> list[MacroEvent]:
    if now.utcoffset() is None:
        raise ValueError("macro gate requires timezone-aware now")

    normalized_currency = currency.upper()
    relevant = [
        event
        for event in events
        if normalized_currency in {item.upper() for item in event.currencies}
    ]
    active: list[MacroEvent] = []
    for event in relevant:
        block_start = event.start_at - timedelta(minutes=event.pre_block_minutes)
        block_end = event.end_at + timedelta(minutes=event.post_block_minutes)
        if block_start <= now <= block_end and event.impact == MacroImpact.HIGH:
            active.append(event)
    return active


def macro_gate_status(
    path: Path,
    now: datetime,
    *,
    currency: str = "USD",
) -> MacroGateStatus:
    events = [
        event
        for event in load_macro_events(path)
        if currency.upper() in {item.upper() for item in event.currencies}
    ]
    active = active_macro_blackouts(events, now, currency=currency)

    future = [
        event
        for event in events
        if event.end_at + timedelta(minutes=event.post_block_minutes) > now
    ]
    next_event = future[0] if future else None

    if active:
        names = ", ".join(event.name for event in active)
        return MacroGateStatus(
            at=now,
            blocked=True,
            active_events=active,
            next_event=next_event,
            reason=f"high-impact macro blackout: {names}",
        )

    return MacroGateStatus(
        at=now,
        blocked=False,
        active_events=[],
        next_event=next_event,
        reason="no high-impact macro blackout is active",
    )


def classify_macro_signal_context(
    events: list[MacroEvent],
    at: datetime,
    *,
    currency: str = "USD",
    post_safe_window_minutes: int = 135,
) -> MacroSignalContext:
    if at.utcoffset() is None:
        raise ValueError("macro signal context requires timezone-aware at")
    if post_safe_window_minutes < 0:
        raise ValueError("post_safe_window_minutes must be non-negative")

    normalized_currency = currency.upper()
    relevant = [
        event
        for event in events
        if event.impact == MacroImpact.HIGH
        and normalized_currency in {item.upper() for item in event.currencies}
    ]

    active_candidates: list[tuple[float, MacroEvent, datetime]] = []
    post_safe_candidates: list[tuple[float, MacroEvent, datetime]] = []
    for event in relevant:
        block_start = event.start_at - timedelta(minutes=event.pre_block_minutes)
        safe_resume = event.end_at + timedelta(minutes=event.post_block_minutes)
        if block_start <= at <= safe_resume:
            minutes = (at - safe_resume).total_seconds() / 60.0
            active_candidates.append((abs(minutes), event, safe_resume))
            continue
        post_safe_end = safe_resume + timedelta(minutes=post_safe_window_minutes)
        if safe_resume < at <= post_safe_end:
            minutes = (at - safe_resume).total_seconds() / 60.0
            post_safe_candidates.append((minutes, event, safe_resume))

    if active_candidates:
        _, event, safe_resume = min(active_candidates, key=lambda item: item[0])
        return MacroSignalContext(
            phase=MacroSignalPhase.BLACKOUT,
            at=at,
            event_id=event.event_id,
            event_name=event.name,
            event_start_at=event.start_at,
            safe_resume_at=safe_resume,
            minutes_from_safe_resume=(
                (at - safe_resume).total_seconds() / 60.0
            ),
            post_safe_window_minutes=post_safe_window_minutes,
        )

    if post_safe_candidates:
        minutes, event, safe_resume = min(
            post_safe_candidates,
            key=lambda item: item[0],
        )
        return MacroSignalContext(
            phase=MacroSignalPhase.POST_SAFE,
            at=at,
            event_id=event.event_id,
            event_name=event.name,
            event_start_at=event.start_at,
            safe_resume_at=safe_resume,
            minutes_from_safe_resume=minutes,
            post_safe_window_minutes=post_safe_window_minutes,
        )

    return MacroSignalContext(
        phase=MacroSignalPhase.NORMAL,
        at=at,
        post_safe_window_minutes=post_safe_window_minutes,
    )
