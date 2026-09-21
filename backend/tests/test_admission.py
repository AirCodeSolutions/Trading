from app.domain.admission import AdmissionState, EvidenceWindow, StrategyEvidence
from app.services.admission import assess_strategy


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
