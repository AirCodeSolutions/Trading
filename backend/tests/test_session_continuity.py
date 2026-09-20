from datetime import UTC, datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.services.session_continuity import reopen_warmup_remaining


START = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)


def bar(at: datetime) -> MarketBar:
    return MarketBar(
        symbol="TEST",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=100,
    )


def test_reopen_requires_three_closed_m5_bars_after_large_gap() -> None:
    bars = [
        bar(START + timedelta(minutes=5 * index))
        for index in range(5)
    ]
    reopen = START + timedelta(hours=3)
    bars.extend(
        [
            bar(reopen),
            bar(reopen + timedelta(minutes=5)),
            bar(reopen + timedelta(minutes=10)),
        ]
    )

    assert reopen_warmup_remaining(bars, 5) == 2
    assert reopen_warmup_remaining(bars, 6) == 1
    assert reopen_warmup_remaining(bars, 7) == 0


def test_normal_m5_continuity_has_no_warmup() -> None:
    bars = [
        bar(START + timedelta(minutes=5 * index))
        for index in range(12)
    ]

    assert reopen_warmup_remaining(bars) == 0


def test_gap_threshold_does_not_trigger_at_exactly_twenty_minutes() -> None:
    bars = [
        bar(START),
        bar(START + timedelta(minutes=20)),
    ]

    assert reopen_warmup_remaining(bars) == 0
