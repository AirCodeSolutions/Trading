from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.opportunity_funnel import OpportunityFunnel, OpportunityFunnelStrategy
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import PaperTradeStatus
from app.services.blocked_probe import load_blocked_probe_state, load_closed_probes


def build_opportunity_funnel(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 24,
    symbols: tuple[str, ...] | None = None,
) -> OpportunityFunnel:
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")

    window_start = now - timedelta(hours=window_hours)
    allowed = {symbol.upper() for symbol in symbols} if symbols else None

    signal_rows: list[ShadowOpportunityDiagnostic] = []
    for path in sorted(runtime_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = ShadowOpportunityDiagnostic.model_validate_json(line)
                except ValueError:
                    continue
                if allowed is not None and row.symbol.upper() not in allowed:
                    continue
                if not (window_start <= row.evaluated_at <= now):
                    continue
                if row.state == ShadowSignalState.NO_SIGNAL:
                    continue
                signal_rows.append(row)

    probes: list[BlockedOpportunityProbe] = []
    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for probe in load_closed_probes(path):
            if allowed is not None and probe.symbol.upper() not in allowed:
                continue
            if window_start <= probe.signal_at <= now:
                probes.append(probe)

    for state_path in sorted(runtime_dir.glob("*_blocked_probe_state.json")):
        state = load_blocked_probe_state(state_path)
        probe = state.open_probe
        if probe is None:
            continue
        if allowed is not None and probe.symbol.upper() not in allowed:
            continue
        if window_start <= probe.signal_at <= now:
            probes.append(probe)

    grouped_signals: dict[str, list[ShadowOpportunityDiagnostic]] = defaultdict(list)
    grouped_probes: dict[str, list[BlockedOpportunityProbe]] = defaultdict(list)

    for row in signal_rows:
        grouped_signals[f"{row.symbol}:{row.mechanism.value}"].append(row)
    for probe in probes:
        grouped_probes[f"{probe.symbol}:{probe.mechanism.value}"].append(probe)

    strategy_ids = sorted(set(grouped_signals) | set(grouped_probes))
    strategies: list[OpportunityFunnelStrategy] = []
    for strategy_id in strategy_ids:
        rows = grouped_signals[strategy_id]
        strategy_probes = grouped_probes[strategy_id]
        sample = rows[0] if rows else strategy_probes[0]
        results = [
            probe.result_r
            for probe in strategy_probes
            if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
        ]
        capitals = [
            probe.required_capital_base_risk_eur
            for probe in strategy_probes
            if probe.required_capital_base_risk_eur > 0
        ]
        reasons = Counter(
            row.base_risk.reason
            for row in rows
            if row.state == ShadowSignalState.SIGNAL_BLOCKED
            and row.base_risk is not None
            and row.base_risk.reason
        )
        strategies.append(
            OpportunityFunnelStrategy(
                strategy_id=strategy_id,
                symbol=sample.symbol,
                mechanism=sample.mechanism,
                signal_rows=len(rows),
                blocked_signal_rows=sum(
                    row.state == ShadowSignalState.SIGNAL_BLOCKED for row in rows
                ),
                executable_signal_rows=sum(
                    row.state == ShadowSignalState.SIGNAL_EXECUTABLE for row in rows
                ),
                tracked_blocked_probes=len(strategy_probes),
                resolved_blocked_probes=len(results),
                open_blocked_probes=sum(
                    probe.status == PaperTradeStatus.OPEN for probe in strategy_probes
                ),
                blocked_wins=sum(result > 0 for result in results),
                blocked_losses=sum(result < 0 for result in results),
                blocked_total_r=sum(results),
                blocked_expectancy_r=(sum(results) / len(results)) if results else 0.0,
                blocked_feasible_under_max_risk=sum(
                    probe.capital_granularity_feasible_under_max_risk
                    for probe in strategy_probes
                ),
                min_required_capital_base_risk_eur=min(capitals) if capitals else None,
                max_required_capital_base_risk_eur=max(capitals) if capitals else None,
                block_reasons=dict(sorted(reasons.items())),
            )
        )

    all_results = [
        probe.result_r
        for probe in probes
        if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
    ]
    all_reasons = Counter(
        row.base_risk.reason
        for row in signal_rows
        if row.state == ShadowSignalState.SIGNAL_BLOCKED
        and row.base_risk is not None
        and row.base_risk.reason
    )

    return OpportunityFunnel(
        window_hours=window_hours,
        window_start=window_start,
        window_end=now,
        signal_rows=len(signal_rows),
        blocked_signal_rows=sum(
            row.state == ShadowSignalState.SIGNAL_BLOCKED for row in signal_rows
        ),
        executable_signal_rows=sum(
            row.state == ShadowSignalState.SIGNAL_EXECUTABLE for row in signal_rows
        ),
        tracked_blocked_probes=len(probes),
        resolved_blocked_probes=len(all_results),
        open_blocked_probes=sum(
            probe.status == PaperTradeStatus.OPEN for probe in probes
        ),
        blocked_wins=sum(result > 0 for result in all_results),
        blocked_losses=sum(result < 0 for result in all_results),
        blocked_total_r=sum(all_results),
        blocked_expectancy_r=(
            sum(all_results) / len(all_results) if all_results else 0.0
        ),
        blocked_feasible_under_max_risk=sum(
            probe.capital_granularity_feasible_under_max_risk for probe in probes
        ),
        block_reasons=dict(sorted(all_reasons.items())),
        strategies=strategies,
    )
