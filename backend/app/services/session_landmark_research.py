from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from app.domain.session_landmark_research import (
    SessionLandmarkLatest,
    SessionLandmarkResearchReport,
    SessionLandmarkSummary,
)
from app.domain.shadow import ShadowOpportunityDiagnostic


def build_session_landmark_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
    symbols: tuple[str, ...] | None = None,
) -> SessionLandmarkResearchReport:
    start = now - timedelta(hours=window_hours)
    allowed = {item.upper() for item in symbols} if symbols else None
    grouped: dict[tuple[str, str], list[ShadowOpportunityDiagnostic]] = defaultdict(list)
    latest: dict[tuple[str, str], ShadowOpportunityDiagnostic] = {}
    legacy = 0
    for path in sorted(runtime_dir.glob("*.jsonl")):
        if path.name.endswith(("_paper_trades.jsonl", "_blocked_probes.jsonl")):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = ShadowOpportunityDiagnostic.model_validate_json(line)
            except ValueError:
                continue
            if allowed and row.symbol.upper() not in allowed:
                continue
            if not start <= row.evaluated_at <= now:
                continue
            context = row.session_landmark_context
            if context is None:
                legacy += 1
                continue
            key = (row.symbol, row.mechanism.value)
            grouped[key].append(row)
            if key not in latest or latest[key].evaluated_at < row.evaluated_at:
                latest[key] = row

    summaries = []
    for (symbol, mechanism), rows in sorted(grouped.items()):
        summaries.append(SessionLandmarkSummary(
            symbol=symbol,
            mechanism=mechanism,
            observable=len(rows),
            winners=0,
            losers=0,
            median_nearest_distance_atr_m5=_median([
                row.session_landmark_context.nearest_landmark_distance_atr_m5 for row in rows
            ]),
            median_nearest_distance_atr_m15=_median([
                row.session_landmark_context.nearest_landmark_distance_atr_m15 for row in rows
            ]),
            median_active_session_position=_median([
                row.session_landmark_context.active_session_position for row in rows
            ]),
        ))
    return SessionLandmarkResearchReport(
        generated_at=now,
        window_hours=window_hours,
        window_start=start,
        window_end=now,
        instrumented_observations=sum(len(rows) for rows in grouped.values()),
        legacy_observations_excluded=legacy,
        summaries=summaries,
        latest=[
            SessionLandmarkLatest(
                symbol=row.symbol,
                mechanism=row.mechanism.value,
                context=row.session_landmark_context.model_dump(mode="json"),
            )
            for row in latest.values()
        ],
        limitations=[
            "Levels use only fully closed M5 bars at or before signal_at.",
            "Historical rows without the prospective context remain excluded.",
            "This report is research-only and does not affect signals, stops, sizing, or admission.",
            "Sweep/reclaim is intentionally omitted until a frozen causal definition is established.",
        ],
    )


def _median(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return median(clean) if clean else None
