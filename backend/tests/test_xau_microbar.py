import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.trading import Side
from app.domain.xau_microbar import XauMicrobarM1
from app.services.xau_microbar import (
    LEDGER_FILE,
    SEQUENCE_SNAPSHOT_FILE,
    STATE_FILE,
    append_xau_microbar,
    capture_xau_sequence_microstructure,
    load_xau_microbar_summary,
    sample_xau_microbar_once,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 24, 10, 0, 0, tzinfo=TZ)


def server_epoch(at: datetime) -> int:
    wall_clock_utc = at.replace(tzinfo=UTC)
    return int(wall_clock_utc.timestamp())


def write_quote(
    files_dir: Path,
    at: datetime,
    *,
    bid: float,
    ask: float,
) -> None:
    path = files_dir / "trading_demo_spec_XAUUSD.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "symbol",
                "bid",
                "ask",
                "digits",
                "contract_size",
                "tick_size",
                "tick_value",
                "point",
                "min_lot",
                "max_lot",
                "lot_step",
                "stop_level",
                "margin_required",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": server_epoch(at),
                "symbol": "XAUUSD",
                "bid": bid,
                "ask": ask,
                "digits": 2,
                "contract_size": 100,
                "tick_size": 0.01,
                "tick_value": 1,
                "point": 0.01,
                "min_lot": 0.01,
                "max_lot": 10000,
                "lot_step": 0.01,
                "stop_level": 0,
                "margin_required": 376,
            }
        )


def test_microbar_aggregates_quotes_and_closes_on_next_minute(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    write_quote(
        files_dir,
        START + timedelta(seconds=1),
        bid=4280.00,
        ask=4280.28,
    )
    first = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
    )
    assert first.closed_bars == 0
    assert first.total_quote_samples == 1
    assert first.current_bar is not None
    assert first.current_bar.mid_open == pytest.approx(4280.14)

    write_quote(
        files_dir,
        START + timedelta(seconds=20),
        bid=4279.50,
        ask=4279.80,
    )
    second = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=21),
    )
    assert second.total_quote_samples == 2
    assert second.current_bar is not None
    assert second.current_bar.bid_low == 4279.50
    assert second.current_bar.ask_low == 4279.80
    assert second.current_bar.quote_count == 2
    assert second.current_bar.mid_up_ticks == 0
    assert second.current_bar.mid_down_ticks == 1
    assert second.current_bar.directional_tick_samples == 1
    assert second.current_bar.mid_tick_imbalance == pytest.approx(-1.0)

    write_quote(
        files_dir,
        START + timedelta(minutes=1, seconds=2),
        bid=4281.00,
        ask=4281.26,
    )
    third = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(minutes=1, seconds=3),
    )

    assert third.closed_bars == 1
    assert third.total_quote_samples == 3
    assert third.latest_closed_bar_at == START
    assert third.recent[0].mid_close == pytest.approx(4279.65)
    assert third.recent[0].quote_count == 2
    assert third.current_bar is not None
    assert third.current_bar.minute_at == START + timedelta(minutes=1)
    assert (runtime_dir / LEDGER_FILE).read_text().count("\n") == 1


def test_microbar_deduplicates_same_broker_timestamp(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    at = START + timedelta(seconds=4)
    write_quote(files_dir, at, bid=4280.0, ask=4280.28)

    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=5),
    )
    repeated = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=6),
    )

    assert repeated.total_quote_samples == 1
    assert repeated.current_bar is not None
    assert repeated.current_bar.quote_count == 1


def test_microbar_rejects_stale_startup_quote_without_backfill(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START - timedelta(minutes=5),
        bid=4280.0,
        ask=4280.28,
    )

    summary = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START,
    )

    assert summary.started_at == START
    assert summary.total_quote_samples == 0
    assert summary.closed_bars == 0
    assert summary.current_bar is None
    assert not (runtime_dir / LEDGER_FILE).exists()
    assert (runtime_dir / STATE_FILE).exists()


def test_microbar_does_not_synthesize_gap_minutes(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START + timedelta(seconds=1),
        bid=4280.0,
        ask=4280.28,
    )
    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
    )

    write_quote(
        files_dir,
        START + timedelta(minutes=4, seconds=1),
        bid=4285.0,
        ask=4285.28,
    )
    summary = sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(minutes=4, seconds=2),
    )

    assert summary.closed_bars == 1
    assert summary.recent[0].minute_at == START
    assert summary.current_bar is not None
    assert summary.current_bar.minute_at == START + timedelta(minutes=4)


def test_microbar_summary_marks_live_quote_healthy(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    write_quote(
        files_dir,
        START + timedelta(seconds=2),
        bid=4280.0,
        ask=4280.28,
    )
    sample_xau_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=3),
    )

    summary = load_xau_microbar_summary(
        runtime_dir,
        now=START + timedelta(seconds=10),
    )

    assert summary.healthy is True
    assert summary.quote_age_seconds == 8.0


def test_microbar_summary_exposes_causal_geometry_windows(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    ledger = runtime_dir / LEDGER_FILE

    closes = [100.5, 101.0, 100.0, 102.0, 103.0, 102.5]
    for index, close in enumerate(closes):
        minute = START + timedelta(minutes=index)
        open_price = 100.0 if index == 0 else closes[index - 1]
        low = min(open_price, close) - 0.25
        high = max(open_price, close) + 0.25
        append_xau_microbar(
            ledger,
            XauMicrobarM1(
                minute_at=minute,
                first_quote_at=minute,
                last_quote_at=minute + timedelta(seconds=59),
                bid_open=open_price - 0.14,
                bid_high=high - 0.14,
                bid_low=low - 0.14,
                bid_close=close - 0.14,
                ask_open=open_price + 0.14,
                ask_high=high + 0.14,
                ask_low=low + 0.14,
                ask_close=close + 0.14,
                mid_open=open_price,
                mid_high=high,
                mid_low=low,
                mid_close=close,
                spread_open=0.28,
                spread_high=0.30,
                spread_low=0.26,
                spread_close=0.28,
                spread_sum=16.8,
                quote_count=60,
                mid_up_ticks=39,
                mid_down_ticks=20,
            ),
        )

    summary = load_xau_microbar_summary(
        runtime_dir,
        now=START + timedelta(minutes=6),
    )

    assert summary.geometry_5m is not None
    assert summary.geometry_5m.bars == 5
    assert summary.geometry_5m.mid_open == pytest.approx(100.5)
    assert summary.geometry_5m.mid_close == pytest.approx(102.5)
    assert summary.geometry_5m.mid_high == pytest.approx(103.25)
    assert summary.geometry_5m.mid_low == pytest.approx(99.75)
    assert summary.geometry_5m.range_price == pytest.approx(3.5)
    assert summary.geometry_5m.signed_move == pytest.approx(2.0)
    assert 0 <= summary.geometry_5m.close_location <= 1
    assert 0 <= summary.geometry_5m.path_efficiency <= 1
    assert summary.geometry_5m.average_spread == pytest.approx(0.28)
    assert summary.geometry_5m.max_spread == pytest.approx(0.30)
    assert summary.geometry_5m.average_quotes_per_bar == pytest.approx(60.0)
    assert summary.geometry_5m.directional_tick_samples == 295
    assert summary.geometry_5m.mid_tick_imbalance == pytest.approx(95 / 295)
    assert summary.geometry_5m.spread_change == pytest.approx(0.0)
    assert summary.geometry_5m.distance_to_low == pytest.approx(2.75)
    assert summary.geometry_5m.distance_to_high == pytest.approx(0.75)

    assert summary.geometry_15m is not None
    assert summary.geometry_15m.bars == 6
    assert summary.geometry_15m.mid_open == pytest.approx(100.0)
    assert summary.geometry_15m.mid_close == pytest.approx(102.5)


def _diagnostic(
    *,
    latest_closed_m5_at: datetime,
    mechanism: OpportunityMechanism = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
    state: ShadowSignalState = ShadowSignalState.SIGNAL_EXECUTABLE,
) -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="XAUUSD",
        mechanism=mechanism,
        evaluated_at=latest_closed_m5_at + timedelta(minutes=1),
        latest_closed_m5_at=latest_closed_m5_at,
        latest_closed_m15_at=latest_closed_m5_at - timedelta(minutes=10),
        state=state,
        side=Side.SELL,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=8.0,
        atr_ratio=1.0,
        volatility_percentile=0.5,
        momentum_12_atr=0.0,
        efficiency=0.5,
        structural_stop=4300.0,
        target_r=1.0,
        max_holding_bars=12,
        reason="test signal",
    )


def test_sequence_snapshot_is_causal_and_idempotent(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    ledger = runtime_dir / LEDGER_FILE

    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 999.0]
    for index, close in enumerate(closes):
        minute = START + timedelta(minutes=index)
        open_price = close - 0.5
        append_xau_microbar(
            ledger,
            XauMicrobarM1(
                minute_at=minute,
                first_quote_at=minute,
                last_quote_at=minute + timedelta(seconds=59),
                bid_open=open_price - 0.14,
                bid_high=close + 0.11,
                bid_low=open_price - 0.39,
                bid_close=close - 0.14,
                ask_open=open_price + 0.14,
                ask_high=close + 0.39,
                ask_low=open_price - 0.11,
                ask_close=close + 0.14,
                mid_open=open_price,
                mid_high=close + 0.25,
                mid_low=open_price - 0.25,
                mid_close=close,
                spread_open=0.28,
                spread_high=0.30,
                spread_low=0.26,
                spread_close=0.28,
                spread_sum=16.8,
                quote_count=60,
            ),
        )

    diagnostic = _diagnostic(
        latest_closed_m5_at=START,
    )

    assert capture_xau_sequence_microstructure(
        runtime_dir,
        diagnostic,
    ) is True
    assert capture_xau_sequence_microstructure(
        runtime_dir,
        diagnostic,
    ) is False

    summary = load_xau_microbar_summary(
        runtime_dir,
        now=START + timedelta(minutes=6),
    )
    assert summary.sequence_signal_snapshots == 1
    assert len(summary.recent_sequence_signals) == 1
    snapshot = summary.recent_sequence_signals[0]
    assert snapshot.signal_at == START + timedelta(minutes=5)
    assert snapshot.latest_microbar_at == START + timedelta(minutes=4)
    assert snapshot.geometry_5m is not None
    assert snapshot.geometry_5m.mid_close == pytest.approx(104.0)
    assert snapshot.geometry_5m.mid_close != pytest.approx(999.0)


def test_sequence_snapshot_ignores_non_signal_and_non_sequence(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    assert capture_xau_sequence_microstructure(
        runtime_dir,
        _diagnostic(
            latest_closed_m5_at=START,
            state=ShadowSignalState.NO_SIGNAL,
        ),
    ) is False
    assert capture_xau_sequence_microstructure(
        runtime_dir,
        _diagnostic(
            latest_closed_m5_at=START,
            mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        ),
    ) is False
    assert not (runtime_dir / SEQUENCE_SNAPSHOT_FILE).exists()
