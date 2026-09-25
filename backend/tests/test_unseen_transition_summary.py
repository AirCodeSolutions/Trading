import pytest

from app.domain.trading import Side
from app.domain.xau_microbar import (
    XauMicrobarGeometry,
    XauUnseenTransitionSnapshot,
)
from app.services.xau_unseen_transition_capture import (
    summarize_unseen_tick_pressure_snapshots,
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



def _geometry(
    *,
    imbalance: float | None,
    directional_ticks: int,
) -> XauMicrobarGeometry:
    return XauMicrobarGeometry.model_construct(
        directional_tick_samples=directional_ticks,
        mid_tick_imbalance=imbalance,
    )


def _pressure_snapshot(
    episode_id: str,
    *,
    side: Side,
    imbalance_5m: float | None,
    ticks_5m: int,
    imbalance_15m: float | None,
    ticks_15m: int,
    aligned: bool | None,
) -> XauUnseenTransitionSnapshot:
    return XauUnseenTransitionSnapshot.model_construct(
        episode_id=episode_id,
        episode_side=side,
        geometry_5m=_geometry(
            imbalance=imbalance_5m,
            directional_ticks=ticks_5m,
        ),
        geometry_15m=_geometry(
            imbalance=imbalance_15m,
            directional_ticks=ticks_15m,
        ),
        transition_aligned=aligned,
    )


def test_unseen_tick_pressure_summary_is_side_adjusted_and_prospective() -> None:
    rows = [
        _pressure_snapshot(
            "buy-aligned",
            side=Side.BUY,
            imbalance_5m=0.4,
            ticks_5m=100,
            imbalance_15m=0.2,
            ticks_15m=300,
            aligned=True,
        ),
        _pressure_snapshot(
            "sell-aligned",
            side=Side.SELL,
            imbalance_5m=-0.2,
            ticks_5m=80,
            imbalance_15m=-0.1,
            ticks_15m=240,
            aligned=True,
        ),
        _pressure_snapshot(
            "buy-opposed",
            side=Side.BUY,
            imbalance_5m=-0.6,
            ticks_5m=60,
            imbalance_15m=-0.4,
            ticks_15m=180,
            aligned=False,
        ),
        _pressure_snapshot(
            "legacy-no-pressure",
            side=Side.SELL,
            imbalance_5m=None,
            ticks_5m=0,
            imbalance_15m=None,
            ticks_15m=0,
            aligned=True,
        ),
        _pressure_snapshot(
            "unresolved",
            side=Side.SELL,
            imbalance_5m=-0.1,
            ticks_5m=40,
            imbalance_15m=0.2,
            ticks_15m=120,
            aligned=None,
        ),
    ]

    summary = summarize_unseen_tick_pressure_snapshots("btcusd", rows)

    assert summary.symbol == "BTCUSD"
    assert summary.episodes_with_tick_pressure == 4
    assert summary.resolved_with_tick_pressure == 3
    assert summary.aligned_with_tick_pressure == 2
    assert summary.opposed_with_tick_pressure == 1
    assert summary.unresolved_with_tick_pressure == 1
    assert summary.median_directional_tick_samples_5m == pytest.approx(70)
    assert summary.median_side_aligned_tick_imbalance_5m == pytest.approx(0.15)
    assert summary.median_aligned_side_tick_imbalance_5m == pytest.approx(0.3)
    assert summary.median_opposed_side_tick_imbalance_5m == pytest.approx(-0.6)
    assert summary.median_directional_tick_samples_15m == pytest.approx(210)
    assert summary.median_aligned_side_tick_imbalance_15m == pytest.approx(0.15)
    assert summary.median_opposed_side_tick_imbalance_15m == pytest.approx(-0.4)


def test_unseen_tick_pressure_summary_excludes_legacy_zero_tick_rows() -> None:
    rows = [
        _pressure_snapshot(
            "legacy",
            side=Side.BUY,
            imbalance_5m=None,
            ticks_5m=0,
            imbalance_15m=None,
            ticks_15m=0,
            aligned=True,
        )
    ]

    summary = summarize_unseen_tick_pressure_snapshots("XAUUSD", rows)

    assert summary.episodes_with_tick_pressure == 0
    assert summary.resolved_with_tick_pressure == 0
    assert summary.median_side_aligned_tick_imbalance_5m is None
    assert summary.median_side_aligned_tick_imbalance_15m is None
