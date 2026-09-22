from app.domain.causal_economic_matrix import DirectionalConsistency
from app.services.causal_economic_matrix import _directional_consistency


def test_directional_consistency_classification() -> None:
    assert (
        _directional_consistency(0.6, 0.55, 0.7)
        == DirectionalConsistency.ALIGNED_STABLE
    )
    assert (
        _directional_consistency(0.4, 0.45, 0.3)
        == DirectionalConsistency.OPPOSED_STABLE
    )
    assert (
        _directional_consistency(0.6, 0.45, 0.7)
        == DirectionalConsistency.MIXED
    )
    assert (
        _directional_consistency(0.6, None, 0.7)
        == DirectionalConsistency.INSUFFICIENT
    )
