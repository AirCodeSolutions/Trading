from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.opportunity_funnel import (
    BlockedProbeOutcomeSummary,
    OpportunityFunnel,
    OpportunityFunnelStrategy,
    ResearchProbeCandidateProgress,
    ResearchProbeQualification,
    ResearchProbeQualificationState,
)
from app.domain.portfolio import ProspectiveQualificationState
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperSummary, ShadowPaperTrade
from app.services.blocked_probe import load_blocked_probe_state, load_closed_probes
from app.services.prospective_qualification import MIN_PROSPECTIVE_TRADES, assess_prospective
from app.services.shadow_paper import load_closed_trades, load_shadow_paper_state

_CAPITAL_BLOCK_REASON = "minimum broker lot exceeds the risk budget"
_EPSILON = 1e-12


def build_opportunity_funnel(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 24,
    symbols: tuple[str, ...] | None = None,
    reference_capital_eur: float = 400.0,
    base_risk_fraction: float = 0.01,
    absolute_max_risk_fraction: float = 0.02,
) -> OpportunityFunnel:
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")
    if reference_capital_eur <= 0:
        raise ValueError("reference_capital_eur must be positive")
    if not 0 < base_risk_fraction <= 1:
        raise ValueError("base_risk_fraction must be between 0 and 1")
    if not 0 < absolute_max_risk_fraction <= 1:
        raise ValueError("absolute_max_risk_fraction must be between 0 and 1")
    if base_risk_fraction > absolute_max_risk_fraction:
        raise ValueError("base risk cannot exceed absolute max risk")

    base_risk_budget_eur = reference_capital_eur * base_risk_fraction
    absolute_max_risk_budget_eur = (
        reference_capital_eur * absolute_max_risk_fraction
    )
    window_start = now - timedelta(hours=window_hours)
    allowed = {symbol.upper() for symbol in symbols} if symbols else None

    signal_rows = _load_signal_rows(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=allowed,
    )
    probes = _load_probes(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=allowed,
    )
    unqualified_probes = _load_unqualified_probes(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=allowed,
    )
    all_unqualified_probes = _load_all_unqualified_probes(
        runtime_dir,
        allowed=allowed,
    )

    grouped_signals: dict[str, list[ShadowOpportunityDiagnostic]] = defaultdict(list)
    grouped_probes: dict[str, list[BlockedOpportunityProbe]] = defaultdict(list)
    grouped_unqualified: dict[str, list[ShadowPaperTrade]] = defaultdict(list)
    grouped_unqualified_all: dict[str, list[ShadowPaperTrade]] = defaultdict(list)

    for row in signal_rows:
        grouped_signals[f"{row.symbol}:{row.mechanism.value}"].append(row)
    for probe in probes:
        grouped_probes[f"{probe.symbol}:{probe.mechanism.value}"].append(probe)
    for probe in unqualified_probes:
        grouped_unqualified[f"{probe.symbol}:{probe.mechanism.value}"].append(probe)
    for probe in all_unqualified_probes:
        grouped_unqualified_all[f"{probe.symbol}:{probe.mechanism.value}"].append(probe)

    strategy_ids = sorted(
        set(grouped_signals)
        | set(grouped_probes)
        | set(grouped_unqualified)
        | set(grouped_unqualified_all)
    )
    strategies: list[OpportunityFunnelStrategy] = []
    for strategy_id in strategy_ids:
        rows = grouped_signals[strategy_id]
        strategy_probes = grouped_probes[strategy_id]
        strategy_unqualified = grouped_unqualified[strategy_id]
        strategy_unqualified_all = grouped_unqualified_all[strategy_id]
        sample = (
            rows[0]
            if rows
            else strategy_probes[0]
            if strategy_probes
            else strategy_unqualified[0]
            if strategy_unqualified
            else strategy_unqualified_all[0]
        )
        results = _resolved_results(strategy_probes)
        unqualified_results = _resolved_trade_results(strategy_unqualified)
        unqualified_qualification = _assess_unqualified_probe_evidence(
            strategy_id,
            strategy_unqualified_all,
        )
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
        capital_metrics = _capital_metrics(
            strategy_probes,
            base_risk_budget_eur=base_risk_budget_eur,
            absolute_max_risk_budget_eur=absolute_max_risk_budget_eur,
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
                tracked_unqualified_probes=len(strategy_unqualified),
                resolved_unqualified_probes=len(unqualified_results),
                open_unqualified_probes=sum(
                    probe.status == PaperTradeStatus.OPEN
                    for probe in strategy_unqualified
                ),
                unqualified_probe_wins=sum(
                    result > 0 for result in unqualified_results
                ),
                unqualified_probe_losses=sum(
                    result < 0 for result in unqualified_results
                ),
                unqualified_probe_total_r=sum(unqualified_results),
                unqualified_probe_expectancy_r=(
                    sum(unqualified_results) / len(unqualified_results)
                    if unqualified_results
                    else 0.0
                ),
                unqualified_probe_qualification=unqualified_qualification,
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
                    probe.min_lot_loss_eur <= absolute_max_risk_budget_eur + _EPSILON
                    for probe in strategy_probes
                ),
                capital_limited_probes=capital_metrics["capital_limited_probes"],
                capital_base_feasible_probes=capital_metrics[
                    "capital_base_feasible_probes"
                ],
                capital_max_feasible_probes=capital_metrics[
                    "capital_max_feasible_probes"
                ],
                capital_base_feasible_resolved_probes=capital_metrics[
                    "capital_base_feasible_resolved_probes"
                ],
                capital_base_feasible_wins=capital_metrics[
                    "capital_base_feasible_wins"
                ],
                capital_base_feasible_losses=capital_metrics[
                    "capital_base_feasible_losses"
                ],
                capital_base_feasible_total_r=capital_metrics[
                    "capital_base_feasible_total_r"
                ],
                capital_base_feasible_expectancy_r=capital_metrics[
                    "capital_base_feasible_expectancy_r"
                ],
                min_required_capital_base_risk_eur=min(capitals) if capitals else None,
                max_required_capital_base_risk_eur=max(capitals) if capitals else None,
                block_reasons=dict(sorted(reasons.items())),
                blocked_probe_outcomes_by_reason=_blocked_probe_outcomes_by_reason(
                    strategy_probes
                ),
            )
        )

    research_candidates = [
        row for row in strategies if row.unqualified_probe_qualification is not None
    ]
    most_observed = (
        min(
            research_candidates,
            key=lambda row: (
                -row.unqualified_probe_qualification.closed_trades,
                row.strategy_id,
            ),
        )
        if research_candidates
        else None
    )
    review_ready = sorted(
        (
            row
            for row in research_candidates
            if row.unqualified_probe_qualification is not None
            and row.unqualified_probe_qualification.state
            == ResearchProbeQualificationState.SUPPORTS_REVIEW
        ),
        key=lambda row: row.strategy_id,
    )
    positive_candidates = sorted(
        (
            row
            for row in research_candidates
            if row.unqualified_probe_qualification is not None
            and row.unqualified_probe_qualification.expectancy_r > 0
        ),
        key=lambda row: (
            -row.unqualified_probe_qualification.closed_trades,
            -row.unqualified_probe_qualification.expectancy_r,
            row.strategy_id,
        ),
    )

    all_results = _resolved_results(probes)
    all_unqualified_results = _resolved_trade_results(unqualified_probes)
    all_reasons = Counter(
        row.base_risk.reason
        for row in signal_rows
        if row.state == ShadowSignalState.SIGNAL_BLOCKED
        and row.base_risk is not None
        and row.base_risk.reason
    )
    capital_metrics = _capital_metrics(
        probes,
        base_risk_budget_eur=base_risk_budget_eur,
        absolute_max_risk_budget_eur=absolute_max_risk_budget_eur,
    )

    return OpportunityFunnel(
        window_hours=window_hours,
        window_start=window_start,
        window_end=now,
        reference_capital_eur=reference_capital_eur,
        base_risk_budget_eur=base_risk_budget_eur,
        absolute_max_risk_budget_eur=absolute_max_risk_budget_eur,
        signal_rows=len(signal_rows),
        blocked_signal_rows=sum(
            row.state == ShadowSignalState.SIGNAL_BLOCKED for row in signal_rows
        ),
        executable_signal_rows=sum(
            row.state == ShadowSignalState.SIGNAL_EXECUTABLE for row in signal_rows
        ),
        tracked_unqualified_probes=len(unqualified_probes),
        resolved_unqualified_probes=len(all_unqualified_results),
        open_unqualified_probes=sum(
            probe.status == PaperTradeStatus.OPEN for probe in unqualified_probes
        ),
        unqualified_probe_wins=sum(result > 0 for result in all_unqualified_results),
        unqualified_probe_losses=sum(result < 0 for result in all_unqualified_results),
        unqualified_probe_total_r=sum(all_unqualified_results),
        unqualified_probe_expectancy_r=(
            sum(all_unqualified_results) / len(all_unqualified_results)
            if all_unqualified_results
            else 0.0
        ),
        unqualified_probe_review_ready_strategies=len(review_ready),
        unqualified_probe_review_queue=[
            _candidate_progress(row, grouped_unqualified_all[row.strategy_id])
            for row in review_ready
            if row.unqualified_probe_qualification is not None
        ],
        most_observed_unqualified_candidate=(
            _candidate_progress(
                most_observed,
                grouped_unqualified_all[most_observed.strategy_id],
            )
            if most_observed is not None
            and most_observed.unqualified_probe_qualification is not None
            else None
        ),
        positive_unqualified_candidates=[
            _candidate_progress(row, grouped_unqualified_all[row.strategy_id])
            for row in positive_candidates
            if row.unqualified_probe_qualification is not None
        ],
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
            probe.min_lot_loss_eur <= absolute_max_risk_budget_eur + _EPSILON
            for probe in probes
        ),
        capital_limited_probes=capital_metrics["capital_limited_probes"],
        capital_base_feasible_probes=capital_metrics[
            "capital_base_feasible_probes"
        ],
        capital_max_feasible_probes=capital_metrics["capital_max_feasible_probes"],
        capital_base_feasible_resolved_probes=capital_metrics[
            "capital_base_feasible_resolved_probes"
        ],
        capital_base_feasible_wins=capital_metrics["capital_base_feasible_wins"],
        capital_base_feasible_losses=capital_metrics["capital_base_feasible_losses"],
        capital_base_feasible_total_r=capital_metrics[
            "capital_base_feasible_total_r"
        ],
        capital_base_feasible_expectancy_r=capital_metrics[
            "capital_base_feasible_expectancy_r"
        ],
        block_reasons=dict(sorted(all_reasons.items())),
        blocked_probe_outcomes_by_reason=_blocked_probe_outcomes_by_reason(probes),
        strategies=strategies,
    )


def _load_signal_rows(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[ShadowOpportunityDiagnostic]:
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
                if not (window_start <= row.evaluated_at <= window_end):
                    continue
                if row.state == ShadowSignalState.NO_SIGNAL:
                    continue
                signal_rows.append(row)
    return signal_rows


def _load_probes(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[BlockedOpportunityProbe]:
    probes: list[BlockedOpportunityProbe] = []
    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for probe in load_closed_probes(path):
            if allowed is not None and probe.symbol.upper() not in allowed:
                continue
            if window_start <= probe.signal_at <= window_end:
                probes.append(probe)

    for state_path in sorted(runtime_dir.glob("*_blocked_probe_state.json")):
        state = load_blocked_probe_state(state_path)
        probe = state.open_probe
        if probe is None:
            continue
        if allowed is not None and probe.symbol.upper() not in allowed:
            continue
        if window_start <= probe.signal_at <= window_end:
            probes.append(probe)
    return probes


def _load_unqualified_probes(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[ShadowPaperTrade]:
    probes: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        for probe in load_closed_trades(path):
            if allowed is not None and probe.symbol.upper() not in allowed:
                continue
            if window_start <= probe.signal_at <= window_end:
                probes.append(probe)

    for state_path in sorted(runtime_dir.glob("*_unqualified_probe_state.json")):
        state = load_shadow_paper_state(state_path)
        probe = state.open_trade
        if probe is None:
            continue
        if allowed is not None and probe.symbol.upper() not in allowed:
            continue
        if window_start <= probe.signal_at <= window_end:
            probes.append(probe)
    return probes



def _load_all_unqualified_probes(
    runtime_dir: Path,
    *,
    allowed: set[str] | None,
) -> list[ShadowPaperTrade]:
    probes: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        for probe in load_closed_trades(path):
            if allowed is None or probe.symbol.upper() in allowed:
                probes.append(probe)

    for state_path in sorted(runtime_dir.glob("*_unqualified_probe_state.json")):
        state = load_shadow_paper_state(state_path)
        probe = state.open_trade
        if probe is not None and (allowed is None or probe.symbol.upper() in allowed):
            probes.append(probe)
    return probes


def _assess_unqualified_probe_evidence(
    strategy_id: str,
    probes: list[ShadowPaperTrade],
) -> ResearchProbeQualification | None:
    closed = sorted(
        (
            probe
            for probe in probes
            if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
        ),
        key=lambda probe: probe.signal_at,
    )
    open_probe = next(
        (probe for probe in probes if probe.status == PaperTradeStatus.OPEN),
        None,
    )
    if not closed and open_probe is None:
        return None

    results = [probe.result_r for probe in closed if probe.result_r is not None]
    gains = sum(result for result in results if result > 0)
    losses = -sum(result for result in results if result < 0)
    profit_factor = gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for result in results:
        equity += result
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    summary = ShadowPaperSummary(
        closed_trades=len(closed),
        wins=sum(result > 0 for result in results),
        losses=sum(result < 0 for result in results),
        total_r=sum(results),
        expectancy_r=(sum(results) / len(results)) if results else 0.0,
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        total_pnl_eur=sum(probe.pnl_eur or 0.0 for probe in closed),
        open_trade=open_probe,
    )
    qualification = assess_prospective(strategy_id, summary)
    state = {
        ProspectiveQualificationState.COLLECTING: ResearchProbeQualificationState.COLLECTING,
        ProspectiveQualificationState.FAILED: ResearchProbeQualificationState.FAILED,
        ProspectiveQualificationState.SUPPORTS_DEMO: ResearchProbeQualificationState.SUPPORTS_REVIEW,
    }[qualification.state]
    if state == ResearchProbeQualificationState.COLLECTING:
        reason = (
            f"{qualification.closed_trades}/{MIN_PROSPECTIVE_TRADES} resolved "
            "executable probes; minimum research-review sample not reached"
        )
    elif state == ResearchProbeQualificationState.FAILED:
        reason = qualification.reason.replace(
            "prospective ",
            "prospective executable-probe ",
            1,
        )
    else:
        reason = (
            "prospective executable-probe evidence meets the existing paper "
            "thresholds; dedicated validation is required before any admission change"
        )

    return ResearchProbeQualification(
        state=state,
        closed_trades=qualification.closed_trades,
        minimum_trades=MIN_PROSPECTIVE_TRADES,
        expectancy_r=qualification.expectancy_r,
        profit_factor=qualification.profit_factor,
        max_drawdown_r=qualification.max_drawdown_r,
        reason=reason,
    )


def _candidate_progress(
    row: OpportunityFunnelStrategy,
    all_probes: list[ShadowPaperTrade],
) -> ResearchProbeCandidateProgress:
    qualification = row.unqualified_probe_qualification
    if qualification is None:
        raise ValueError("candidate progress requires probe qualification")
    results = _resolved_trade_results(all_probes)
    remaining = max(0, qualification.minimum_trades - qualification.closed_trades)
    return ResearchProbeCandidateProgress(
        strategy_id=row.strategy_id,
        symbol=row.symbol,
        mechanism=row.mechanism,
        qualification=qualification,
        wins=sum(result > 0 for result in results),
        losses=sum(result < 0 for result in results),
        total_r=sum(results),
        remaining_trades_to_review=remaining,
        sample_progress=min(
            1.0,
            qualification.closed_trades / qualification.minimum_trades,
        ),
    )


def _blocked_probe_outcomes_by_reason(
    probes: list[BlockedOpportunityProbe],
) -> dict[str, BlockedProbeOutcomeSummary]:
    grouped: dict[str, list[BlockedOpportunityProbe]] = defaultdict(list)
    for probe in probes:
        grouped[probe.block_reason].append(probe)

    summaries: dict[str, BlockedProbeOutcomeSummary] = {}
    for reason, reason_probes in sorted(grouped.items()):
        results = _resolved_results(reason_probes)
        total_r = sum(results)
        summaries[reason] = BlockedProbeOutcomeSummary(
            tracked=len(reason_probes),
            resolved=len(results),
            open=sum(
                probe.status == PaperTradeStatus.OPEN for probe in reason_probes
            ),
            wins=sum(result > 0 for result in results),
            losses=sum(result < 0 for result in results),
            total_r=total_r,
            expectancy_r=(total_r / len(results) if results else 0.0),
        )
    return summaries


def _resolved_results(probes: list[BlockedOpportunityProbe]) -> list[float]:
    return [
        probe.result_r
        for probe in probes
        if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
    ]


def _resolved_trade_results(probes: list[ShadowPaperTrade]) -> list[float]:
    return [
        probe.result_r
        for probe in probes
        if probe.status != PaperTradeStatus.OPEN and probe.result_r is not None
    ]


def _capital_metrics(
    probes: list[BlockedOpportunityProbe],
    *,
    base_risk_budget_eur: float,
    absolute_max_risk_budget_eur: float,
) -> dict[str, int | float]:
    capital_limited = [
        probe for probe in probes if probe.block_reason == _CAPITAL_BLOCK_REASON
    ]
    base_feasible = [
        probe
        for probe in capital_limited
        if probe.min_lot_loss_eur <= base_risk_budget_eur + _EPSILON
    ]
    max_feasible = [
        probe
        for probe in capital_limited
        if probe.min_lot_loss_eur <= absolute_max_risk_budget_eur + _EPSILON
    ]
    base_results = _resolved_results(base_feasible)
    base_total_r = sum(base_results)
    return {
        "capital_limited_probes": len(capital_limited),
        "capital_base_feasible_probes": len(base_feasible),
        "capital_max_feasible_probes": len(max_feasible),
        "capital_base_feasible_resolved_probes": len(base_results),
        "capital_base_feasible_wins": sum(result > 0 for result in base_results),
        "capital_base_feasible_losses": sum(result < 0 for result in base_results),
        "capital_base_feasible_total_r": base_total_r,
        "capital_base_feasible_expectancy_r": (
            base_total_r / len(base_results) if base_results else 0.0
        ),
    }
