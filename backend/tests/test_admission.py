from app.domain.admission import AdmissionState, EvidenceWindow, StrategyEvidence
from app.services.admission import assess_strategy, demo_collection_allowed, paper_entry_allowed


def window(
    trades: int,
    expectancy: float,
    profit_factor: float = 1.2,
    drawdown: float = 5.0,
) -> EvidenceWindow:
    return EvidenceWindow(
        trades=trades,
        expectancy_r=expectancy,
        profit_factor=profit_factor,
        max_drawdown_r=drawdown,
    )


def test_strategy_stays_shadow_without_enough_independent_evidence() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, 0.2),
            validation=window(20, 0.2),
            holdout=window(10, 0.2),
        )
    )
    assert result.state == AdmissionState.SHADOW
    assert result.paper_collection_candidate is True


def test_strategy_is_rejected_when_holdout_expectancy_is_negative() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, 0.2),
            validation=window(60, 0.1),
            holdout=window(30, -0.01),
        )
    )
    assert result.state == AdmissionState.REJECTED


def test_strategy_can_only_activate_with_positive_validation_and_holdout() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, 0.2),
            validation=window(60, 0.08, profit_factor=1.18, drawdown=6),
            holdout=window(30, 0.05, profit_factor=1.11, drawdown=7),
        )
    )
    assert result.state == AdmissionState.ACTIVE



def test_shadow_paper_candidate_requires_positive_train_and_validation() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, -0.01),
            validation=window(20, 0.2),
            holdout=window(1, 0.5),
        )
    )

    assert result.state == AdmissionState.SHADOW
    assert result.paper_collection_candidate is False


def test_sparse_negative_holdout_can_still_collect_paper_when_train_validation_positive() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(50, 0.20),
            validation=window(8, 0.40),
            holdout=window(1, -0.24),
        )
    )

    assert result.state == AdmissionState.SHADOW
    assert result.paper_collection_candidate is True
    assert result.weakest_expectancy_r == -0.24


def test_rejected_strategy_is_never_marked_as_paper_collection_candidate() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, 0.2),
            validation=window(60, 0.1),
            holdout=window(30, -0.01),
        )
    )

    assert result.state == AdmissionState.REJECTED
    assert result.paper_collection_candidate is False


def test_active_strategy_does_not_need_shadow_collection_candidate_flag() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, 0.2),
            validation=window(60, 0.08, profit_factor=1.18, drawdown=6),
            holdout=window(30, 0.05, profit_factor=1.11, drawdown=7),
        )
    )

    assert result.state == AdmissionState.ACTIVE
    assert result.paper_collection_candidate is False


def test_demo_collection_allows_positive_weakest_shadow() -> None:
    result = assess_strategy(
        StrategyEvidence(
            strategy_id="candidate",
            train=window(200, -0.1),
            validation=window(20, 0.30),
            holdout=window(10, 0.20),
        )
    )

    assert result.state == AdmissionState.SHADOW
    assert result.paper_collection_candidate is False
    assert paper_entry_allowed(result) is True
    assert demo_collection_allowed(result) is True


def test_demo_collection_never_allows_rejected_or_active_via_shadow_path() -> None:
    rejected = assess_strategy(
        StrategyEvidence(
            strategy_id="rejected",
            train=window(200, 0.2),
            validation=window(60, 0.1),
            holdout=window(30, -0.01),
        )
    )
    active = assess_strategy(
        StrategyEvidence(
            strategy_id="active",
            train=window(200, 0.2),
            validation=window(60, 0.08, profit_factor=1.18),
            holdout=window(30, 0.05, profit_factor=1.11),
        )
    )

    assert demo_collection_allowed(rejected) is False
    assert demo_collection_allowed(active) is False
