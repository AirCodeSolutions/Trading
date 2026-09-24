from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    MarketOpportunityEpisode,
    OpportunityCaptureState,
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityDetectionStage,
)
from app.domain.xau_microbar import XauMicrobarM1
from app.services.trading_intelligence import _atr_series
from app.services.xau_unseen_transition_capture import (
    UNSEEN_TRANSITION_FILE,
    append_xau_unseen_transition_snapshot,
    build_xau_unseen_transition_snapshot,
    load_xau_unseen_transition_snapshots,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 24, 10, 0, tzinfo=TZ)


def _m5_bars(count: int = 12) -> list[MarketBar]:
    rows = []
    close = 100.0
    for index in range(count):
        at = START + timedelta(minutes=5 * index)
        rows.append(
            MarketBar(
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                timestamp=at,
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close + 0.5,
                volume=100,
            )
        )
        close += 0.5
    return rows


def _m1_rows(count: int = 31) -> list[XauMicrobarM1]:
    rows = []
    for index in range(count):
        minute = START + timedelta(minutes=index)
        mid = 100.0 + index
        rows.append(
            XauMicrobarM1(
                minute_at=minute,
                first_quote_at=minute,
                last_quote_at=minute + timedelta(seconds=59),
                bid_open=mid - 0.14,
                bid_high=mid + 0.11,
                bid_low=mid - 0.39,
                bid_close=mid - 0.14,
                ask_open=mid + 0.14,
                ask_high=mid + 0.39,
                ask_low=mid - 0.11,
                ask_close=mid + 0.14,
                mid_open=mid,
                mid_high=mid + 0.25,
                mid_low=mid - 0.25,
                mid_close=mid,
                spread_open=0.28,
                spread_high=0.30,
                spread_low=0.26,
                spread_close=0.28,
                spread_sum=16.8,
                quote_count=60,
            )
        )
    return rows


def _episode() -> MarketOpportunityEpisode:
    return MarketOpportunityEpisode(
        episode_id="XAUUSD-episode-1",
        symbol="XAUUSD",
        side=Side.BUY,
        birth_at=START + timedelta(minutes=25),
        horizon_end_at=START + timedelta(minutes=85),
        reference_price=102.5,
        atr_m5=2.0,
        move_atr=2.2,
        capture_state=OpportunityCaptureState.MISSED,
        detection_stage=OpportunityDetectionStage.UNSEEN,
        causal_context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.UNCLASSIFIED,
        ),
    )


def test_unseen_snapshot_uses_only_m1_closed_by_birth(
    monkeypatch,
) -> None:
    bars = _m5_bars()
    atr = _atr_series(bars)
    context = OpportunityCausalContext(
        pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        side=Side.BUY,
        aligned_with_move=True,
    )
    monkeypatch.setattr(
        "app.services.xau_unseen_transition_capture.first_directional_transition",
        lambda *args, **kwargs: (6, context),
    )

    snapshot = build_xau_unseen_transition_snapshot(
        _episode(),
        bars,
        atr,
        _m1_rows(),
    )

    assert snapshot is not None
    assert snapshot.geometry_5m is not None
    assert snapshot.geometry_5m.mid_close == pytest.approx(124.0)
    assert snapshot.latest_microbar_at == START + timedelta(minutes=24)
    assert snapshot.transition_pattern == OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT
    assert snapshot.transition_side == Side.BUY
    assert snapshot.transition_bars_waited == 2
    assert snapshot.transition_aligned is True
    assert snapshot.move_consumed_atr is not None


def test_unseen_snapshot_rejects_non_target_episode() -> None:
    episode = _episode().model_copy(
        update={"detection_stage": OpportunityDetectionStage.PRECURSOR_ONLY}
    )

    assert build_xau_unseen_transition_snapshot(
        episode,
        _m5_bars(),
        _atr_series(_m5_bars()),
        _m1_rows(),
    ) is None


def test_unseen_transition_ledger_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / UNSEEN_TRANSITION_FILE
    bars = _m5_bars()
    snapshot = build_xau_unseen_transition_snapshot(
        _episode(),
        bars,
        _atr_series(bars),
        _m1_rows(),
    )
    assert snapshot is not None

    assert append_xau_unseen_transition_snapshot(path, snapshot) is True
    assert append_xau_unseen_transition_snapshot(path, snapshot) is False

    rows = load_xau_unseen_transition_snapshots(path)
    assert len(rows) == 1
    assert rows[0].episode_id == snapshot.episode_id
