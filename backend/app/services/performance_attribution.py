from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.performance_attribution import AttributionCohort, PerformanceAttributionReport
from app.domain.shadow import ShadowOpportunityDiagnostic
from app.domain.shadow_paper import ShadowPaperTrade
from app.services.blocked_probe import load_closed_probes
from app.services.mt4_csv import _server_timezone

_DIMENSIONS = (
    "symbol", "mechanism", "side", "session", "hour", "weekday", "regime",
    "stop_geometry_source", "nearest_landmark_type",
)
_INTERACTIONS = (
    ("symbol", "mechanism"),
    ("mechanism", "session"),
    ("mechanism", "hour"),
    ("mechanism", "regime"),
    ("mechanism", "side"),
    ("symbol", "stop_geometry_source"),
    ("mechanism", "nearest_landmark_type"),
)


def build_performance_attribution_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
    symbols: tuple[str, ...] | None = None,
) -> PerformanceAttributionReport:
    start = now - timedelta(hours=window_hours)
    allowed = {symbol.upper() for symbol in symbols} if symbols else None
    diagnostics = _load_diagnostics(runtime_dir, start, now, allowed)
    joined = _load_resolved_rows(runtime_dir, start, now, allowed, diagnostics)
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in joined:
        population = str(row["population"])
        for dimension in _DIMENSIONS:
            value = row.get(dimension)
            if value is not None:
                groups[(population, dimension, str(value))].append(row)
    summaries = [_cohort(population, dimension, value, rows) for (population, dimension, value), rows in sorted(groups.items())]
    interactions = []
    for population in sorted({str(row["population"]) for row in joined}):
        for first, second in _INTERACTIONS:
            grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
            for row in joined:
                if row["population"] == population and row.get(first) is not None and row.get(second) is not None:
                    grouped[(str(row[first]), str(row[second]))].append(row)
            for (value_first, value_second), rows in sorted(grouped.items()):
                interactions.append(_cohort(population, f"{first} x {second}", f"{value_first} × {value_second}", rows))
    return PerformanceAttributionReport(
        generated_at=now,
        window_hours=window_hours,
        window_start=start,
        window_end=now,
        populations={population: sum(row["result_r"] is not None for row in joined if row["population"] == population) for population in ("admitted", "unqualified_probe", "blocked_probe")},
        summaries=summaries,
        interactions=interactions,
        limitations=[
            "Populations are kept separate: admitted, executable unqualified probes, and blocked probes.",
            "Missing post-entry and early-context fields remain missing; legacy rows are not backfilled.",
            "Cohorts are descriptive and do not rank strategies or create trading filters.",
            "Only the seven predefined interactions are emitted; no combinatorial feature search is performed.",
        ],
    )


def _load_diagnostics(runtime_dir: Path, start: datetime, now: datetime, allowed: set[str] | None) -> dict[tuple[str, str, str], ShadowOpportunityDiagnostic]:
    result = {}
    for path in sorted(runtime_dir.glob("*.jsonl")):
        if path.name.endswith(("_paper_trades.jsonl", "_unqualified_probes.jsonl", "_blocked_probes.jsonl")):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = ShadowOpportunityDiagnostic.model_validate_json(line)
            except ValueError:
                continue
            if allowed and row.symbol.upper() not in allowed or not start <= row.evaluated_at <= now:
                continue
            result[(row.symbol, row.mechanism.value, (row.latest_closed_m5_at + timedelta(minutes=5)).isoformat())] = row
    return result


def _load_resolved_rows(runtime_dir: Path, start: datetime, now: datetime, allowed: set[str] | None, diagnostics: dict[tuple[str, str, str], ShadowOpportunityDiagnostic]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(runtime_dir.glob("*_paper_trades.jsonl")):
        population = "admitted" if "_unqualified_" not in path.name else "unqualified_probe"
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                trade = ShadowPaperTrade.model_validate_json(line)
            except ValueError:
                continue
            if trade.result_r is None or not start <= trade.signal_at <= now or allowed and trade.symbol.upper() not in allowed:
                continue
            rows.append(_row_from_trade(trade, population, diagnostics))
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                trade = ShadowPaperTrade.model_validate_json(line)
            except ValueError:
                continue
            if trade.result_r is None or not start <= trade.signal_at <= now or allowed and trade.symbol.upper() not in allowed:
                continue
            rows.append(_row_from_trade(trade, "unqualified_probe", diagnostics))
    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for probe in load_closed_probes(path):
            if probe.result_r is None or not start <= probe.signal_at <= now or allowed and probe.symbol.upper() not in allowed:
                continue
            rows.append(_row_from_probe(probe, diagnostics))
    return rows


def _base(row, population: str, diagnostics):
    key = (row.symbol, row.mechanism.value, row.signal_at.isoformat())
    diagnostic = diagnostics.get(key)
    context = getattr(row, "session_landmark_context", None)
    if context is None and diagnostic is not None:
        context = diagnostic.session_landmark_context
    at = row.signal_at.astimezone(_server_timezone())
    return {
        "population": population, "symbol": row.symbol, "mechanism": row.mechanism.value,
        "side": row.side.value.upper(), "session": context.active_session if context else None,
        "hour": f"{at.hour:02d}:00", "weekday": at.strftime("%A"),
        "regime": diagnostic.regime.value if diagnostic else None,
        "stop_geometry_source": diagnostic.stop_geometry_source.value if diagnostic and diagnostic.stop_geometry_source else None,
        "nearest_landmark_type": context.nearest_landmark_type if context else None,
        "result_r": row.result_r, "holding_bars": row.bars_held, "signal_at": row.signal_at,
        "spread_to_stop": diagnostic.base_risk.spread_to_stop if diagnostic and diagnostic.base_risk else None,
        "stop_atr_m15": diagnostic.structural_stop_atr_m15 if diagnostic else None,
    }


def _row_from_trade(trade: ShadowPaperTrade, population: str, diagnostics):
    return _base(trade, population, diagnostics)


def _row_from_probe(probe: BlockedOpportunityProbe, diagnostics):
    return _base(probe, "blocked_probe", diagnostics)


def _cohort(population: str, dimension: str, value: str, rows: list[dict[str, object]]) -> AttributionCohort:
    values = [float(row["result_r"]) for row in rows if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    total = sum(values) if values else None
    positive_sum = sum(wins)
    negative_sum = abs(sum(losses))
    ordered = [value for _, value in sorted(((row.get("signal_at"), row["result_r"]) for row in rows if row.get("result_r") is not None), key=lambda item: str(item[0]))]
    peak = 0.0
    equity = 0.0
    drawdown = 0.0
    for result_value in ordered:
        equity += float(result_value)
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return AttributionCohort(
        population=population, dimension=dimension, value=value, observations=len(values),
        wins=len(wins), losses=len(losses), win_rate=len(wins) / len(values) if values else None,
        total_r=total, expectancy_r=total / len(values) if values else None,
        profit_factor=positive_sum / negative_sum if negative_sum else None,
        max_drawdown_r=drawdown, median_win_r=median(wins) if wins else None,
        median_loss_r=median(losses) if losses else None,
        median_holding_bars=_median([row.get("holding_bars") for row in rows]),
        median_spread_to_stop=_median([row.get("spread_to_stop") for row in rows]),
        median_stop_atr_m15=_median([row.get("stop_atr_m15") for row in rows]),
        best_results_r=sorted(values, reverse=True)[:3], worst_results_r=sorted(values)[:3],
        opposite_results=sum(value <= 0 for value in wins) + sum(value >= 0 for value in losses),
    )


def _median(values) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return median(clean) if clean else None
