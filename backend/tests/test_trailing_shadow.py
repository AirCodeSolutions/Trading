from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.services.shadow_paper import append_closed_trade
from app.services.trailing_shadow import (
    LEDGER_FILE,
    PAPER_TRADES_FILE,
    advance_trailing_shadow_once,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 23, 18, 0, tzinfo=TZ)


def make_trade(
    trade_id: str,
    *,
    opened_at: datetime,
    entry_at: datetime,
) -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id=trade_id,
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=entry_at,
        entry_bar_at=entry_at,
        opened_at=opened_at,
        entry_price=100.0,
        stop_price=98.0,
        target_price=102.0,
        spread_at_entry=0.0,
        lots=0.01,
        risk_eur=2.0,
        risk_distance=2.0,
        target_r=1.0,
        max_holding_bars=6,
        status=PaperTradeStatus.TARGET,
        exit_at=entry_at + timedelta(minutes=15),
        exit_price=102.0,
        result_r=1.0,
        pnl_eur=2.0,
        bars_held=4,
    )


def make_bars(entry_at: datetime) -> list[MarketBar]:
    values = [
        (100.0, 100.8, 99.9, 100.6),
        (100.6, 101.4, 100.5, 101.2),
        (101.2, 101.8, 101.1, 101.6),
        (101.6, 103.2, 101.5, 103.0),
        (103.0, 103.1, 102.8, 102.9),
        (102.9, 103.0, 102.7, 102.8),
    ]
    return [
        MarketBar(
            symbol="BTCUSD",
            timeframe=Timeframe.M5,
            timestamp=entry_at + timedelta(minutes=5 * index),
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=100,
        )
        for index, (open_, high, low, close) in enumerate(values)
    ]


def patch_history(monkeypatch, bars: list[MarketBar]) -> None:
    monkeypatch.setattr(
        "app.services.trailing_shadow.resolve_mt4_history_path",
        lambda *args, **kwargs: Path("/tmp/fake.csv"),
    )
    monkeypatch.setattr(
        "app.services.trailing_shadow.read_mt4_csv",
        lambda *args, **kwargs: bars,
    )


def test_trailing_shadow_is_prospective_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    initial = advance_trailing_shadow_once(
        files_dir,
        runtime_dir,
        NOW,
    )
    assert initial.started_at == NOW
    assert initial.resolved == 0

    entry_at = NOW + timedelta(minutes=5)
    old_trade = make_trade(
        "old",
        opened_at=NOW - timedelta(minutes=5),
        entry_at=entry_at,
    )
    new_trade = make_trade(
        "new",
        opened_at=NOW + timedelta(minutes=1),
        entry_at=entry_at,
    )
    append_closed_trade(runtime_dir / PAPER_TRADES_FILE, old_trade)
    append_closed_trade(runtime_dir / PAPER_TRADES_FILE, new_trade)
    patch_history(monkeypatch, make_bars(entry_at))

    summary = advance_trailing_shadow_once(
        files_dir,
        runtime_dir,
        NOW + timedelta(hours=1),
    )

    assert summary.resolved == 1
    assert summary.improved == 1
    assert summary.worsened == 0
    assert summary.trailing_total_r == 1.5
    assert summary.static_total_r == 1.0
    assert summary.expectancy_delta_r == 0.5
    assert summary.total_adjustments >= 1
    assert summary.recent[0].trade_id == "new"
    assert (runtime_dir / LEDGER_FILE).read_text().count("\n") == 1

    repeated = advance_trailing_shadow_once(
        files_dir,
        runtime_dir,
        NOW + timedelta(hours=2),
    )
    assert repeated.resolved == 1
    assert (runtime_dir / LEDGER_FILE).read_text().count("\n") == 1


def test_trailing_shadow_waits_for_complete_horizon(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    advance_trailing_shadow_once(files_dir, runtime_dir, NOW)

    entry_at = NOW + timedelta(minutes=5)
    append_closed_trade(
        runtime_dir / PAPER_TRADES_FILE,
        make_trade(
            "new",
            opened_at=NOW + timedelta(minutes=1),
            entry_at=entry_at,
        ),
    )
    patch_history(monkeypatch, make_bars(entry_at)[:5])

    summary = advance_trailing_shadow_once(
        files_dir,
        runtime_dir,
        NOW + timedelta(hours=1),
    )

    assert summary.resolved == 0
    assert not (runtime_dir / LEDGER_FILE).exists()
