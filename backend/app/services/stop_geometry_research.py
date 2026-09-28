from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from app.core.config import settings
from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.stop_geometry import StopGeometryResearchReport, StopGeometrySummary
from app.services.blocked_probe import load_closed_probes


def build_stop_geometry_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
    symbols: tuple[str, ...] | None = None,
) -> StopGeometryResearchReport:
    start = now - timedelta(hours=window_hours)
    allowed = {item.upper() for item in symbols} if symbols else None
    diagnostics: list[ShadowOpportunityDiagnostic] = []
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
            if row.stop_geometry_source is None:
                legacy += 1
            else:
                diagnostics.append(row)

    blocked: list[BlockedOpportunityProbe] = []
    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for row in load_closed_probes(path):
            if allowed and row.symbol.upper() not in allowed:
                continue
            if start <= row.signal_at <= now and row.stop_geometry_source is not None:
                blocked.append(row)

    grouped: dict[tuple[str, object, object], list[ShadowOpportunityDiagnostic]] = defaultdict(list)
    for row in diagnostics:
        grouped[(row.symbol, row.mechanism, row.stop_geometry_source)].append(row)
    blocked_grouped: dict[tuple[str, object, object], list[BlockedOpportunityProbe]] = defaultdict(
        list
    )
    for row in blocked:
        blocked_grouped[(row.symbol, row.mechanism, row.stop_geometry_source)].append(row)

    summaries = []
    for key in sorted(set(grouped) | set(blocked_grouped), key=str):
        rows = grouped[key]
        probes = blocked_grouped[key]
        source = key[2]
        assert source is not None
        additional_m5 = []
        additional_m15 = []
        for probe in probes:
            minimum = probe.spread_at_entry / settings.max_spread_to_stop
            extra = max(0.0, minimum - probe.risk_distance)
            if probe.atr_m5 and probe.atr_m5 > 0:
                additional_m5.append(extra / probe.atr_m5)
            if probe.atr_m15 and probe.atr_m15 > 0:
                additional_m15.append(extra / probe.atr_m15)
        results = [probe.result_r for probe in probes if probe.result_r is not None]
        summaries.append(
            StopGeometrySummary(
                symbol=key[0],
                mechanism=key[1],
                source=source,
                total_instrumented=len(rows),
                spread_blocked=len(probes),
                executable=sum(row.state == ShadowSignalState.SIGNAL_EXECUTABLE for row in rows),
                median_stop_atr_m5=_median([row.structural_stop_atr_m5 for row in rows]),
                median_stop_atr_m15=_median([row.structural_stop_atr_m15 for row in rows]),
                median_spread_atr_m5=_median([row.spread_atr_m5 for row in rows]),
                median_spread_atr_m15=_median([row.spread_atr_m15 for row in rows]),
                median_spread_to_stop=_median(
                    [probe.spread_at_entry / probe.risk_distance for probe in probes]
                ),
                median_additional_distance_atr_m5=_median(additional_m5),
                median_additional_distance_atr_m15=_median(additional_m15),
                blocked_wins=sum(result > 0 for result in results),
                blocked_losses=sum(result < 0 for result in results),
                blocked_total_r=sum(results),
                blocked_expectancy_r=(sum(results) / len(results)) if results else 0.0,
            )
        )
    return StopGeometryResearchReport(
        generated_at=now,
        window_hours=window_hours,
        window_start=start,
        window_end=now,
        instrumented_observations=len(diagnostics),
        legacy_observations_excluded=legacy,
        summaries=summaries,
        limitations=[
            "Only post-instrumentation observations contain stop provenance.",
            "Historical legacy rows remain excluded rather than backfilled.",
            "Additional stop distance is descriptive and never changes the stop or sizing.",
        ],
    )


def _median(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return median(clean) if clean else None
