from app.domain.execution_aware_sequence_research import (
    ExecutionAwareConsistency,
    ExecutionAwareSplitSummary,
)
from app.services.execution_aware_sequence_research import _execution_consistency


def summary(executed: int, expectancy_r: float) -> ExecutionAwareSplitSummary:
    return ExecutionAwareSplitSummary(
        occurrences=executed,
        executed=executed,
        rejected_macro=0,
        rejected_sizing=0,
        rejected_other=0,
        total_r=executed * expectancy_r,
        expectancy_r=expectancy_r,
        profit_factor=1.2 if expectancy_r > 0 else 0.8,
        win_rate=0.55 if expectancy_r > 0 else 0.45,
        max_drawdown_r=2.0,
        average_execution_cost_r=0.1,
        asset_baseline_expectancy_r=-0.05,
        expectancy_delta_vs_baseline_r=expectancy_r + 0.05,
    )


def test_execution_consistency_requires_minimum_support() -> None:
    assert (
        _execution_consistency(
            summary(29, 0.1),
            summary(10, 0.1),
            summary(5, 0.1),
        )
        == ExecutionAwareConsistency.INSUFFICIENT
    )


def test_execution_consistency_marks_positive_stable() -> None:
    assert (
        _execution_consistency(
            summary(30, 0.05),
            summary(10, 0.02),
            summary(5, 0.01),
        )
        == ExecutionAwareConsistency.POSITIVE_STABLE
    )


def test_execution_consistency_marks_negative_stable() -> None:
    assert (
        _execution_consistency(
            summary(30, -0.05),
            summary(10, -0.02),
            summary(5, -0.01),
        )
        == ExecutionAwareConsistency.NEGATIVE_STABLE
    )


def test_execution_consistency_marks_mixed() -> None:
    assert (
        _execution_consistency(
            summary(30, 0.05),
            summary(10, -0.02),
            summary(5, 0.01),
        )
        == ExecutionAwareConsistency.MIXED
    )
