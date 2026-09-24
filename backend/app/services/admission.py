from app.domain.admission import (
    AdmissionDecision,
    AdmissionState,
    StrategyEvidence,
)

MIN_VALIDATION_TRADES = 40
MIN_HOLDOUT_TRADES = 20
MIN_PROFIT_FACTOR = 1.05
MAX_DRAWDOWN_R = 12.0


def assess_strategy(evidence: StrategyEvidence) -> AdmissionDecision:
    windows = (evidence.validation, evidence.holdout)
    weakest_expectancy = min(window.expectancy_r for window in windows)
    worst_drawdown = max(window.max_drawdown_r for window in windows)
    shadow_collection_candidate = (
        evidence.train.expectancy_r > 0
        and evidence.validation.expectancy_r > 0
        and (
            evidence.holdout.trades == 0
            or evidence.holdout.expectancy_r >= 0
        )
    )

    if (
        evidence.validation.trades < MIN_VALIDATION_TRADES
        or evidence.holdout.trades < MIN_HOLDOUT_TRADES
    ):
        return AdmissionDecision(
            strategy_id=evidence.strategy_id,
            state=AdmissionState.SHADOW,
            reason="insufficient independent validation evidence",
            weakest_expectancy_r=weakest_expectancy,
            worst_drawdown_r=worst_drawdown,
            paper_collection_candidate=shadow_collection_candidate,
        )

    if any(window.expectancy_r <= 0 for window in windows):
        return AdmissionDecision(
            strategy_id=evidence.strategy_id,
            state=AdmissionState.REJECTED,
            reason="non-positive expectancy in validation or holdout",
            weakest_expectancy_r=weakest_expectancy,
            worst_drawdown_r=worst_drawdown,
            paper_collection_candidate=False,
        )

    if any(window.profit_factor < MIN_PROFIT_FACTOR for window in windows):
        return AdmissionDecision(
            strategy_id=evidence.strategy_id,
            state=AdmissionState.REJECTED,
            reason="profit factor fails independent evidence floor",
            weakest_expectancy_r=weakest_expectancy,
            worst_drawdown_r=worst_drawdown,
            paper_collection_candidate=False,
        )

    if worst_drawdown > MAX_DRAWDOWN_R:
        return AdmissionDecision(
            strategy_id=evidence.strategy_id,
            state=AdmissionState.REJECTED,
            reason="drawdown exceeds admission policy",
            weakest_expectancy_r=weakest_expectancy,
            worst_drawdown_r=worst_drawdown,
            paper_collection_candidate=False,
        )

    return AdmissionDecision(
        strategy_id=evidence.strategy_id,
        state=AdmissionState.ACTIVE,
        reason="validation and holdout satisfy the initial admission contract",
        weakest_expectancy_r=weakest_expectancy,
        worst_drawdown_r=worst_drawdown,
        paper_collection_candidate=False,
    )


def paper_entry_allowed(admission: AdmissionDecision | None) -> bool:
    if admission is None or admission.state == AdmissionState.REJECTED:
        return False
    if admission.state == AdmissionState.ACTIVE:
        return True
    return (
        admission.weakest_expectancy_r > 0
        or admission.paper_collection_candidate
    )


def demo_collection_allowed(admission: AdmissionDecision | None) -> bool:
    return (
        admission is not None
        and admission.state == AdmissionState.SHADOW
        and paper_entry_allowed(admission)
    )
