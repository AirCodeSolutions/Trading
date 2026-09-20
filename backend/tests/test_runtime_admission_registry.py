from pathlib import Path

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity import (
    OpportunityBacktestResult,
    OpportunityMechanism,
    PerformanceSummary,
    PortfolioResearchResult,
)
from app.services.runtime_admission_registry import (
    load_research_admissions,
    save_research_admissions,
)


def summary() -> PerformanceSummary:
    return PerformanceSummary(
        trades=1,
        total_r=1,
        expectancy_r=1,
        profit_factor=2,
        win_rate=1,
        max_drawdown_r=0,
        total_pnl_eur=2,
        average_execution_cost_r=0.1,
    )


def test_round_trip_research_admissions(tmp_path: Path) -> None:
    decision = AdmissionDecision(
        strategy_id="BTCUSD:break_retest_reaccel",
        state=AdmissionState.SHADOW,
        reason="collect",
        weakest_expectancy_r=0.1,
        worst_drawdown_r=1,
    )
    item = OpportunityBacktestResult(
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        candidates=1,
        executed=1,
        rejected=0,
        rejection_reasons={},
        train=summary(),
        validation=summary(),
        holdout=summary(),
        admission=decision,
    )
    result = PortfolioResearchResult(
        results=[item],
        skipped_symbols={},
        qualified_strategy_id=None,
        selection_reason="none",
    )
    path = tmp_path / "strategy_admissions.json"

    save_research_admissions(path, result)
    loaded = load_research_admissions(path)

    assert loaded["BTCUSD:break_retest_reaccel"].state == AdmissionState.SHADOW
