from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism, TradeOutcome
from app.domain.regime_session_attribution import (
    AttributionDimension,
    AttributionWindow,
)
from app.domain.trading import Side
from app.services.regime import classify_regime
from app.services.regime_session_attribution import (
    REGIME_PARTITION,
    SESSION_PARTITION,
    _bucket,
    _regime_at,
    _window,
)
from app.services.session_landmarks import active_session_at

TZ = ZoneInfo("Europe/Athens")
BASE = datetime(2026, 9, 10, 0, 0, tzinfo=TZ)


def m15(index: int, *, shock: bool = False) -> MarketBar:
    price = 100.0 + index * 0.05
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        timestamp=BASE + timedelta(minutes=15 * index),
        open=price,
        high=price + (5.0 if shock else 0.2),
        low=price - 0.2,
        close=price + (4.5 if shock else 0.05),
        volume=100,
    )


def outcome(at: datetime, result_r: float) -> TradeOutcome:
    return TradeOutcome(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=at,
        entry_at=at,
        exit_at=at + timedelta(minutes=5),
        lots=1.0,
        risk_eur=100.0,
        result_r=result_r,
        pnl_eur=result_r * 100.0,
        execution_cost_r=0.05,
        exit_reason="target" if result_r > 0 else "stop",
    )


def test_fixed_session_partition_matches_canonical_precedence() -> None:
    assert SESSION_PARTITION == ("asia", "london", "us", "transition")
    assert active_session_at(BASE.replace(hour=3)) == "asia"
    assert active_session_at(BASE.replace(hour=11)) == "london"
    # London deliberately owns the overlap 15:30-18:00 in the existing contract.
    assert active_session_at(BASE.replace(hour=16)) == "london"
    assert active_session_at(BASE.replace(hour=19)) == "us"
    assert active_session_at(BASE.replace(hour=23)) == "transition"


def test_regime_at_is_causal_and_ignores_future_m15() -> None:
    bars = [m15(index) for index in range(70)]
    at = bars[60].timestamp + timedelta(minutes=15)
    baseline = _regime_at(bars, at)
    closed = [bar for bar in bars if bar.timestamp + timedelta(minutes=15) <= at]
    assert baseline == classify_regime(closed).regime

    future = [
        *bars,
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M15,
            timestamp=at + timedelta(minutes=15),
            open=100,
            high=130,
            low=90,
            close=128,
            volume=100,
        ),
    ]
    assert _regime_at(future, at) == baseline
    assert baseline in REGIME_PARTITION


def test_bucket_metrics_are_chronological_and_descriptive() -> None:
    rows = [
        outcome(BASE + timedelta(hours=1), 1.5),
        outcome(BASE + timedelta(hours=2), -1.0),
        outcome(BASE + timedelta(hours=3), 0.5),
    ]
    bucket = _bucket(
        window=AttributionWindow.VALIDATION,
        dimension=AttributionDimension.SESSION,
        key="london",
        outcomes=rows,
    )
    assert bucket.trades == 3
    assert bucket.wins == 2
    assert bucket.losses == 1
    assert bucket.total_r == 1.0
    assert abs((bucket.expectancy_r or 0) - (1 / 3)) < 1e-12
    assert bucket.profit_factor == 2.0
    assert bucket.max_drawdown_r == 1.0
    assert abs((bucket.average_execution_cost_r or 0) - 0.05) < 1e-12


def test_window_excludes_train_and_keeps_validation_holdout_separate() -> None:
    train_end = BASE + timedelta(days=1)
    validation_end = BASE + timedelta(days=2)
    assert _window(
        outcome(BASE, 1.0),
        train_end=train_end,
        validation_end=validation_end,
    ) is None
    assert _window(
        outcome(train_end, 1.0),
        train_end=train_end,
        validation_end=validation_end,
    ) == AttributionWindow.VALIDATION
    assert _window(
        outcome(validation_end, 1.0),
        train_end=train_end,
        validation_end=validation_end,
    ) == AttributionWindow.HOLDOUT
