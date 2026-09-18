from datetime import UTC, datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.domain.regime import MarketRegime
from app.services.regime import classify_regime
from app.services.replay import RegimeReplay


def make_bars(count: int = 60) -> list[MarketBar]:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    bars: list[MarketBar] = []
    price = 100.0
    for index in range(count):
        close = price + 0.2
        bars.append(
            MarketBar(
                symbol="TEST",
                timeframe=Timeframe.M15,
                timestamp=start + timedelta(minutes=15 * index),
                open=price,
                high=close + 0.15,
                low=price - 0.15,
                close=close,
                volume=100,
            )
        )
        price = close
    return bars


def test_regime_requires_warmup() -> None:
    snapshot = classify_regime(make_bars(10))
    assert snapshot.regime == MarketRegime.WARMUP


def test_large_directional_information_bar_is_post_shock() -> None:
    bars = make_bars(59)
    previous = bars[-1]
    bars.append(
        MarketBar(
            symbol="TEST",
            timeframe=Timeframe.M15,
            timestamp=previous.timestamp + timedelta(minutes=15),
            open=previous.close,
            high=previous.close + 3.1,
            low=previous.close - 0.1,
            close=previous.close + 3.0,
            volume=500,
        )
    )

    snapshot = classify_regime(bars)

    assert snapshot.regime == MarketRegime.POST_SHOCK
    assert snapshot.direction == 1
    assert snapshot.shock_ratio >= 1.5


def test_batch_and_incremental_replay_are_equivalent() -> None:
    bars = make_bars(75)

    batch = RegimeReplay().replay(bars)

    incremental_engine = RegimeReplay()
    incremental = [incremental_engine.push(bar) for bar in bars]

    assert [item.model_dump() for item in batch] == [
        item.model_dump() for item in incremental
    ]
