import pytest

from app.domain.xau_microbar import XauUnseenTransitionSnapshot
from app.services.xau_unseen_transition_capture import (
    summarize_unseen_transition_snapshots,
)


def _snapshot(
    episode_id: str,
    *,
    aligned: bool | None,
    waited: int | None,
    consumed: float | None,
) -> XauUnseenTransitionSnapshot:
    return XauUnseenTransitionSnapshot.model_construct(
        episode_id=episode_id,
        transition_aligned=aligned,
        transition_bars_waited=waited,
        move_consumed_atr=consumed,
    )


def test_unseen_transition_summary_separates_unresolved_from_direction() -> None:
    rows = [
        _snapshot("a", aligned=True, waited=1, consumed=0.2),
        _snapshot("b", aligned=True, waited=3, consumed=0.8),
        _snapshot("c", aligned=False, waited=2, consumed=-0.5),
        _snapshot("d", aligned=None, waited=None, consumed=None),
    ]

    summary = summarize_unseen_transition_snapshots("xauusd", rows)

    assert summary.symbol == "XAUUSD"
    assert summary.episodes == 4
    assert summary.resolved == 3
    assert summary.aligned == 2
    assert summary.opposed == 1
    assert summary.unresolved == 1
    assert summary.alignment_rate == pytest.approx(2 / 3)
    assert summary.median_transition_bars == 2
    assert summary.median_move_consumed_atr == pytest.approx(0.2)
    assert summary.median_aligned_move_consumed_atr == pytest.approx(0.5)


def test_unseen_transition_summary_keeps_empty_sample_explicit() -> None:
    summary = summarize_unseen_transition_snapshots("BTCUSD", [])

    assert summary.episodes == 0
    assert summary.resolved == 0
    assert summary.alignment_rate is None
    assert summary.median_transition_bars is None
    assert summary.median_move_consumed_atr is None
