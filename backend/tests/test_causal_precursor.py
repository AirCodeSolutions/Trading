from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityDetectionStage,
)
from app.services.causal_precursor import (
    advance_causal_precursors_once,
    load_causal_precursor_collection_state,
    load_causal_precursors,
)
from app.services.trading_intelligence import _market_opportunity_episodes

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 23, 10, 0, tzinfo=TZ)


def _bars(symbol: str = "EURUSD") -> list[MarketBar]:
    rows: list[MarketBar] = []
    for index in range(32):
        price = 1.1000 + 0.00005 * index
        rows.append(
            MarketBar(
                symbol=symbol,
                timeframe=Timeframe.M5,
                timestamp=START + timedelta(minutes=5 * index),
                open=price,
                high=price + 0.0002,
                low=price - 0.0002,
                close=price,
                volume=100,
            )
        )
    return rows


def test_precursor_collection_starts_prospectively_and_deduplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bars = _bars()
    evaluated_at = bars[-1].timestamp + timedelta(minutes=5)
    monkeypatch.setattr(
        "app.services.causal_precursor.load_closed_market_bars",
        lambda *args, **kwargs: bars,
    )
    monkeypatch.setattr(
        "app.services.trading_intelligence._atr_series",
        lambda values: [0.001] * len(values),
    )
    monkeypatch.setattr(
        "app.services.trading_intelligence._classify_causal_context",
        lambda **kwargs: OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.BUY,
            return_3_atr=0.8,
            body_fraction=0.7,
            evidence=["test precursor"],
        ),
    )

    first = advance_causal_precursors_once(
        tmp_path,
        tmp_path,
        evaluated_at,
        symbols=("EURUSD",),
    )
    second = advance_causal_precursors_once(
        tmp_path,
        tmp_path,
        evaluated_at + timedelta(seconds=30),
        symbols=("EURUSD",),
    )

    assert first == 1
    assert second == 0
    state = load_causal_precursor_collection_state(tmp_path)
    assert state is not None
    assert state.started_at == evaluated_at
    rows = load_causal_precursors(
        tmp_path,
        window_start=evaluated_at - timedelta(minutes=1),
        window_end=evaluated_at + timedelta(minutes=1),
    )
    assert len(rows) == 1
    assert rows[0].first_seen_at == evaluated_at
    assert rows[0].pattern == OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT
    assert rows[0].side == Side.BUY


def test_market_opportunity_uses_earliest_aligned_prebirth_precursor() -> None:
    bars = _bars()
    # Force a large up move after index 13 so the first market episode is BUY.
    for index in range(15, 24):
        current = bars[index]
        bars[index] = current.model_copy(
            update={
                "close": current.close + 0.0020,
                "high": current.high + 0.0022,
            }
        )

    birth_at = bars[13].timestamp + timedelta(minutes=5)
    early = CausalPrecursorObservation(
        symbol="EURUSD",
        first_seen_at=birth_at - timedelta(minutes=10),
        latest_closed_m5_at=birth_at - timedelta(minutes=15),
        pattern=OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH,
            side=Side.BUY,
        ),
    )
    later = early.model_copy(
        update={
            "first_seen_at": birth_at - timedelta(minutes=5),
            "latest_closed_m5_at": birth_at - timedelta(minutes=10),
            "pattern": OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            "context": OpportunityCausalContext(
                pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
                side=Side.BUY,
            ),
        }
    )
    opposed = early.model_copy(
        update={
            "first_seen_at": birth_at - timedelta(minutes=15),
            "latest_closed_m5_at": birth_at - timedelta(minutes=20),
            "side": Side.SELL,
        }
    )
    postbirth = early.model_copy(
        update={
            "first_seen_at": birth_at + timedelta(minutes=5),
            "latest_closed_m5_at": birth_at,
        }
    )

    episodes = _market_opportunity_episodes(
        symbol="EURUSD",
        bars=bars,
        signals=[],
        precursors=[opposed, later, postbirth, early],
        window_start=START,
        window_end=START + timedelta(hours=4),
        threshold_atr=1.5,
        horizon_bars=12,
    )

    assert episodes
    first = episodes[0]
    assert first.side == Side.BUY
    assert first.precursor_first_seen_at == early.first_seen_at
    assert first.precursor_pattern == OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH
    assert first.precursor_lead_minutes == 10.0
    assert first.precursor_observations == 2
    assert first.detection_stage == OpportunityDetectionStage.PRECURSOR_ONLY

    unseen = _market_opportunity_episodes(
        symbol="EURUSD",
        bars=bars,
        signals=[],
        precursors=[],
        window_start=START,
        window_end=START + timedelta(hours=4),
        threshold_atr=1.5,
        horizon_bars=12,
    )
    assert unseen[0].detection_stage == OpportunityDetectionStage.UNSEEN
