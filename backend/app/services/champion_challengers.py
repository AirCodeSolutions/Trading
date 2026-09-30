from collections.abc import Sequence

from app.domain.asset_specialization import AssetSpecializationSnapshot
from app.domain.champion_challengers import (
    ChallengerEvidenceState,
    ChallengerReport,
    ChampionChallengerFamilyReport,
    ChampionChallengerReport,
    ChampionReport,
    EconomicChangeAxis,
    EvidenceChecklist,
    VariantMetrics,
)
from app.domain.opportunity import OpportunityMechanism
from app.domain.position_manager import PositionManagerComparison, PositionManagerReport
from app.services.prospective_qualification import (
    MAX_DRAWDOWN_R,
    MIN_PROFIT_FACTOR,
    MIN_PROSPECTIVE_TRADES,
)

_CHALLENGERS = (
    ("TRIGGER_V2", EconomicChangeAxis.ENTRY_TIMING),
    ("ENTRY_ZONE_V2", EconomicChangeAxis.ENTRY_EXECUTION),
    ("POSITION_MANAGER_V2", EconomicChangeAxis.EXIT_MANAGEMENT),
)


def _average(values: Sequence[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return sum(available) / len(available) if available else None


def _pf(values: Sequence[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return 99.0 if gains > 0 and losses == 0 else gains / losses if losses else 0.0


def _dd(values: Sequence[float]) -> float:
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def _pm_rows(report: PositionManagerReport | None, symbol: str, mechanism: OpportunityMechanism) -> list[PositionManagerComparison]:
    if report is None:
        return []
    return [row for row in report.comparisons if row.symbol == symbol and row.mechanism == mechanism and not row.pending and not row.invalid_data and row.baseline_result_r is not None and row.v2_result_r is not None and row.delta_r is not None]


def _pm_metrics(rows: Sequence[PositionManagerComparison], challenger: bool) -> VariantMetrics:
    values = [(row.v2_result_r if challenger else row.baseline_result_r) for row in rows]
    values = [value for value in values if value is not None]
    return VariantMetrics(
        trades=len(values), total_r=sum(values) if values else None,
        expectancy_r=sum(values) / len(values) if values else None, profit_factor=_pf(values) if values else None,
        max_drawdown_r=_dd(values) if values else None,
        average_mfe_capture=_average([row.v2_mfe_capture if challenger else row.baseline_mfe_capture for row in rows]),
        average_giveback_r=_average([row.v2_giveback_r if challenger else row.baseline_giveback_r for row in rows]),
    )


def _pm_state(rows: Sequence[PositionManagerComparison], conflicted: bool) -> tuple[ChallengerEvidenceState, str]:
    if conflicted:
        return ChallengerEvidenceState.CONFLICTED, "asset evidence alignment is conflicted"
    if len(rows) < MIN_PROSPECTIVE_TRADES:
        return ChallengerEvidenceState.COLLECTING if rows else ChallengerEvidenceState.NO_EVIDENCE, "paired PM outcome evidence is below the review population" if rows else "paired outcome evidence not available"
    baseline = _pm_metrics(rows, False)
    challenger = _pm_metrics(rows, True)
    supports = challenger.expectancy_r is not None and challenger.expectancy_r > 0 and challenger.profit_factor is not None and challenger.profit_factor >= MIN_PROFIT_FACTOR and challenger.max_drawdown_r is not None and challenger.max_drawdown_r <= MAX_DRAWDOWN_R and challenger.total_r is not None and baseline.total_r is not None and challenger.total_r > baseline.total_r
    return (ChallengerEvidenceState.REVIEWABLE, "PM V2 improves the same paired population and meets existing review gates") if supports else (ChallengerEvidenceState.DOES_NOT_SUPPORT_REVIEW, "PM V2 does not improve the same paired population under existing review gates")


def build_champion_challenger_report(
    asset_snapshots: Sequence[AssetSpecializationSnapshot],
    position_manager_report: PositionManagerReport | None = None,
) -> ChampionChallengerReport:
    families: list[ChampionChallengerFamilyReport] = []
    for asset in asset_snapshots:
        for evidence in asset.mechanism_evidence:
            if not evidence.compatible:
                continue
            rows = _pm_rows(position_manager_report, asset.symbol, evidence.mechanism)
            baseline = ChampionReport(
                historical_state=evidence.historical_state.value if evidence.historical_state else None,
                historical_weakest_expectancy_r=evidence.weakest_historical_expectancy_r,
                historical_worst_drawdown_r=evidence.historical_worst_drawdown_r,
                prospective_state=evidence.prospective_state, paper_n=evidence.paper_n,
                paper_expectancy_r=evidence.paper_expectancy_r, paper_profit_factor=evidence.paper_profit_factor,
                paper_max_drawdown_r=evidence.paper_max_drawdown_r, paper_total_r=evidence.paper_total_r,
            )
            challengers: list[ChallengerReport] = []
            for variant_id, axis in _CHALLENGERS:
                state = ChallengerEvidenceState.NO_EVIDENCE
                reason = "paired outcome evidence not available"
                baseline_metrics = VariantMetrics()
                challenger_metrics = VariantMetrics()
                if variant_id == "POSITION_MANAGER_V2":
                    state, reason = _pm_state(rows, evidence.evidence_alignment.value == "conflicted")
                    baseline_metrics, challenger_metrics = _pm_metrics(rows, False), _pm_metrics(rows, True)
                challengers.append(ChallengerReport(
                    variant_id=variant_id, economic_axis=axis, evidence_state=state,
                    paired_n=len(rows) if variant_id == "POSITION_MANAGER_V2" else 0,
                    baseline_metrics=baseline_metrics, challenger_metrics=challenger_metrics,
                    delta_total_r=challenger_metrics.total_r - baseline_metrics.total_r if challenger_metrics.total_r is not None and baseline_metrics.total_r is not None else None,
                    delta_expectancy_r=challenger_metrics.expectancy_r - baseline_metrics.expectancy_r if challenger_metrics.expectancy_r is not None and baseline_metrics.expectancy_r is not None else None,
                    delta_profit_factor=challenger_metrics.profit_factor - baseline_metrics.profit_factor if challenger_metrics.profit_factor is not None and baseline_metrics.profit_factor is not None else None,
                    delta_drawdown_r=challenger_metrics.max_drawdown_r - baseline_metrics.max_drawdown_r if challenger_metrics.max_drawdown_r is not None and baseline_metrics.max_drawdown_r is not None else None,
                    delta_mfe_capture=challenger_metrics.average_mfe_capture - baseline_metrics.average_mfe_capture if challenger_metrics.average_mfe_capture is not None and baseline_metrics.average_mfe_capture is not None else None,
                    delta_giveback_r=challenger_metrics.average_giveback_r - baseline_metrics.average_giveback_r if challenger_metrics.average_giveback_r is not None and baseline_metrics.average_giveback_r is not None else None,
                    evidence=EvidenceChecklist(prospective_paired_available=bool(rows) if variant_id == "POSITION_MANAGER_V2" else False),
                    reason=reason,
                ))
            families.append(ChampionChallengerFamilyReport(
                family_id=f"{asset.symbol}:{evidence.mechanism.value}", symbol=asset.symbol, mechanism=evidence.mechanism,
                asset_profile_status=asset.profile_status, asset_role=evidence.role, compatibility=evidence.compatible,
                evidence_alignment=evidence.evidence_alignment, champion=baseline, challengers=challengers,
                evidence_gaps=["historical paired challenger replay unavailable"] if not rows else [],
            ))
    counts = {state: sum(challenger.evidence_state == state for family in families for challenger in family.challengers) for state in ChallengerEvidenceState}
    return ChampionChallengerReport(
        families=families, family_count=len(families), champion_count=len(families),
        challengers_collecting=counts[ChallengerEvidenceState.COLLECTING], challengers_reviewable=counts[ChallengerEvidenceState.REVIEWABLE],
        challengers_does_not_support_review=counts[ChallengerEvidenceState.DOES_NOT_SUPPORT_REVIEW], challengers_conflicted=counts[ChallengerEvidenceState.CONFLICTED],
    )
