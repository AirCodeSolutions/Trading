from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_bar_sources import load_recent_freshest_closed_bars

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=TZ)


def bar(at: datetime) -> MarketBar:
    return MarketBar(
        symbol="EURUSD",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=1.1,
        high=1.101,
        low=1.099,
        close=1.1005,
    )


def test_recent_loader_prefers_fresher_source_over_deeper_stale_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    snapshot = tmp_path / "mt4_bars_EURUSD_M5.json"
    legacy = tmp_path / "EURUSD-M5.csv"
    snapshot.write_text("{}", encoding="utf-8")
    legacy.write_text("placeholder", encoding="utf-8")

    freshest_at = NOW - timedelta(minutes=10)
    stale_last_at = NOW - timedelta(minutes=15)
    snapshot_bars = [bar(freshest_at - timedelta(minutes=5)), bar(freshest_at)]
    legacy_bars = [
        bar(stale_last_at - timedelta(minutes=5 * index))
        for index in reversed(range(20))
    ]

    monkeypatch.setattr(
        "app.services.mt4_bar_sources.read_closed_bar_snapshot",
        lambda *args, **kwargs: snapshot_bars,
    )
    monkeypatch.setattr(
        "app.services.mt4_bar_sources._cached_recent_csv_bars",
        lambda *args, **kwargs: legacy_bars,
    )

    rows = load_recent_freshest_closed_bars(
        tmp_path,
        "EURUSD",
        Timeframe.M5,
        NOW,
        limit=20,
    )

    assert rows[-1].timestamp == freshest_at
    assert len(rows) == 2
