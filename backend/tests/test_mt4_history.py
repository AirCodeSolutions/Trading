from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_history import (
    backfill_m15_prefix_from_m5,
    resolve_mt4_history_path,
)


def test_prefers_closed_bar_research_export(tmp_path: Path) -> None:
    research = tmp_path / "mt4_research_bars_XAUUSD_M5.csv"
    fallback = tmp_path / "XAUUSD-M5.csv"
    research.write_text("research", encoding="utf-8")
    fallback.write_text("fallback", encoding="utf-8")

    result = resolve_mt4_history_path(tmp_path, "xauusd", Timeframe.M5)

    assert result == research


def test_uses_legacy_history_when_research_export_is_missing(tmp_path: Path) -> None:
    fallback = tmp_path / "EURUSD-M15.csv"
    fallback.write_text("fallback", encoding="utf-8")

    result = resolve_mt4_history_path(tmp_path, "eurusd", Timeframe.M15)

    assert result == fallback


START = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def _m5(
    index: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1,
) -> MarketBar:
    return MarketBar(
        symbol="GBPUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _m15(
    minute: int,
    *,
    open_: float = 2.0,
    high: float = 2.2,
    low: float = 1.8,
    close: float = 2.1,
) -> MarketBar:
    return MarketBar(
        symbol="GBPUSD",
        timeframe=Timeframe.M15,
        timestamp=START + timedelta(minutes=minute),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=10,
    )


def test_backfill_aggregates_only_complete_prefix_groups() -> None:
    bars_m5 = [
        _m5(0, open_=1.0, high=1.2, low=0.9, close=1.1, volume=2),
        _m5(1, open_=1.1, high=1.3, low=1.0, close=1.2, volume=3),
        _m5(2, open_=1.2, high=1.4, low=1.1, close=1.3, volume=4),
        _m5(3, open_=1.3, high=1.5, low=1.2, close=1.4, volume=5),
        _m5(4, open_=1.4, high=1.6, low=1.3, close=1.5, volume=6),
        _m5(5, open_=1.5, high=1.7, low=1.4, close=1.6, volume=7),
    ]
    native = [_m15(30)]

    result = backfill_m15_prefix_from_m5(bars_m5, native)

    assert [bar.timestamp for bar in result] == [
        START,
        START + timedelta(minutes=15),
        START + timedelta(minutes=30),
    ]
    first = result[0]
    assert first.timeframe == Timeframe.M15
    assert first.open == 1.0
    assert first.high == 1.4
    assert first.low == 0.9
    assert first.close == 1.3
    assert first.volume == 9


def test_backfill_never_overwrites_native_m15() -> None:
    bars_m5 = [
        _m5(0, open_=1.0, high=1.2, low=0.9, close=1.1),
        _m5(1, open_=1.1, high=1.3, low=1.0, close=1.2),
        _m5(2, open_=1.2, high=1.4, low=1.1, close=1.3),
        _m5(3, open_=9.0, high=9.2, low=8.9, close=9.1),
        _m5(4, open_=9.1, high=9.3, low=9.0, close=9.2),
        _m5(5, open_=9.2, high=9.4, low=9.1, close=9.3),
    ]
    native = [_m15(15, open_=2.0, high=2.5, low=1.5, close=2.2)]

    result = backfill_m15_prefix_from_m5(bars_m5, native)

    assert len(result) == 2
    assert result[1] == native[0]
    assert result[1].open == 2.0


def test_backfill_skips_incomplete_m5_group() -> None:
    bars_m5 = [
        _m5(0, open_=1.0, high=1.2, low=0.9, close=1.1),
        _m5(2, open_=1.2, high=1.4, low=1.1, close=1.3),
    ]
    native = [_m15(15)]

    result = backfill_m15_prefix_from_m5(bars_m5, native)

    assert result == native


def test_no_backfill_when_native_history_already_starts_first() -> None:
    bars_m5 = [
        _m5(3, open_=1.3, high=1.5, low=1.2, close=1.4),
        _m5(4, open_=1.4, high=1.6, low=1.3, close=1.5),
        _m5(5, open_=1.5, high=1.7, low=1.4, close=1.6),
    ]
    native = [_m15(0)]

    result = backfill_m15_prefix_from_m5(bars_m5, native)

    assert result == native
