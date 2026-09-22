from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCaptureState
from app.services.trading_intelligence import (
    _market_opportunity_episodes,
    _trade_metrics,
    build_trading_intelligence,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=TZ)


def bar(at: datetime, o: float, h: float, l: float, c: float) -> MarketBar:
    return MarketBar(
        symbol="EURUSD",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=o,
        high=h,
        low=l,
        close=c,
    )


def diagnostic(
    *,
    at: datetime,
    side: Side,
    state: ShadowSignalState,
) -> ShadowOpportunityDiagnostic:
    sizing = ShadowSizingSnapshot(
        risk_fraction=0.01,
        approved=state == ShadowSignalState.SIGNAL_EXECUTABLE,
        reason="ok" if state == ShadowSignalState.SIGNAL_EXECUTABLE else "blocked",
        lots=0.04 if state == ShadowSignalState.SIGNAL_EXECUTABLE else 0.0,
        expected_loss_eur=4.0 if state == ShadowSignalState.SIGNAL_EXECUTABLE else 0.0,
        spread_to_stop=0.1,
    )
    return ShadowOpportunityDiagnostic(
        symbol="EURUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        evaluated_at=at,
        latest_closed_m5_at=at - timedelta(minutes=5),
        latest_closed_m15_at=at - timedelta(minutes=15),
        state=state,
        side=side,
        regime=MarketRegime.DIRECTIONAL,
        regime_direction=1 if side == Side.BUY else -1,
        atr_m15=0.001,
        atr_ratio=1.0,
        volatility_percentile=0.5,
        efficiency=0.5,
        structural_stop=1.0990 if side == Side.BUY else 1.1010,
        target_r=1.8,
        base_risk=sizing,
        reason="test",
    )


def test_trade_metrics_measure_excursion_and_waiting() -> None:
    signal_at = NOW.replace(hour=10, minute=0)
    opened_at = signal_at + timedelta(minutes=5)
    bars = [
        bar(signal_at, 1.1000, 1.1005, 1.0998, 1.1004),
        bar(signal_at + timedelta(minutes=5), 1.1004, 1.1014, 1.1001, 1.1010),
        bar(signal_at + timedelta(minutes=10), 1.1010, 1.1018, 1.1007, 1.1015),
    ]

    metrics = _trade_metrics(
        side=Side.BUY,
        signal_at=signal_at,
        opened_at=opened_at,
        exit_at=signal_at + timedelta(minutes=15),
        entry_price=1.1006,
        stop_price=1.0996,
        target_price=1.1026,
        risk_distance=0.001,
        spread=0.0001,
        bars=bars,
    )

    assert metrics["signal_entry_price"] == 1.1001
    assert round(float(metrics["r_lost_while_waiting"]), 3) == 0.5
    assert round(float(metrics["mfe_r"]), 3) == 1.2
    assert round(float(metrics["mae_r"]), 3) == 0.5
    assert round(float(metrics["rr_at_signal"]), 3) > 2.0
    assert round(float(metrics["rr_at_entry"]), 3) == 2.0
    assert round(float(metrics["mfe_consumed_before_entry_r"]), 3) == 0.4


def test_market_opportunity_capture_states() -> None:
    start = NOW.replace(hour=8, minute=0)
    bars = []
    price = 1.1000
    for i in range(30):
        at = start + timedelta(minutes=5 * i)
        close = price + (0.00005 * i)
        high = close + 0.0002
        low = close - 0.0002
        bars.append(bar(at, close, high, low, close))
    # Force a large upward move after the first eligible birth.
    for i in range(15, 24):
        b = bars[i]
        bars[i] = b.model_copy(
            update={
                "open": b.open,
                "close": b.close + 0.0020,
                "high": b.high + 0.0022,
                "low": b.low,
            }
        )

    birth_at = bars[13].timestamp + timedelta(minutes=5)
    executable_signal = diagnostic(
        at=birth_at + timedelta(minutes=5),
        side=Side.BUY,
        state=ShadowSignalState.SIGNAL_EXECUTABLE,
    )
    episodes = _market_opportunity_episodes(
        symbol="EURUSD",
        bars=bars,
        signals=[executable_signal],
        window_start=start,
        window_end=NOW,
        threshold_atr=1.5,
        horizon_bars=12,
    )

    assert episodes
    assert episodes[0].capture_state == OpportunityCaptureState.EXECUTABLE
    assert episodes[0].matching_strategies == ["EURUSD:break_retest_reaccel"]

    missed = _market_opportunity_episodes(
        symbol="EURUSD",
        bars=bars,
        signals=[],
        window_start=start,
        window_end=NOW,
        threshold_atr=1.5,
        horizon_bars=12,
    )
    assert missed[0].capture_state == OpportunityCaptureState.MISSED


def test_build_intelligence_aggregates_paper_probe_and_market_denominator(
    tmp_path: Path,
    monkeypatch,
) -> None:
    signal_at = NOW - timedelta(hours=3)
    paper = ShadowPaperTrade(
        trade_id="paper-1",
        symbol="EURUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=Side.BUY,
        signal_at=signal_at,
        entry_bar_at=signal_at,
        opened_at=signal_at,
        entry_price=1.1000,
        stop_price=1.0990,
        target_price=1.1018,
        spread_at_entry=0.0001,
        lots=0.04,
        risk_eur=4.0,
        risk_distance=0.001,
        target_r=1.8,
        max_holding_bars=12,
        status=PaperTradeStatus.TARGET,
        exit_at=signal_at + timedelta(minutes=20),
        exit_price=1.1018,
        result_r=1.8,
        pnl_eur=7.2,
        bars_held=4,
    )
    (tmp_path / "EURUSD_break_retest_paper_trades.jsonl").write_text(
        paper.model_dump_json() + "\n",
        encoding="utf-8",
    )
    probe = BlockedOpportunityProbe(
        probe_id="probe-1",
        symbol="EURUSD",
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        side=Side.SELL,
        signal_at=signal_at + timedelta(minutes=30),
        opened_at=signal_at + timedelta(minutes=30),
        entry_price=1.1010,
        stop_price=1.1020,
        target_price=1.0995,
        spread_at_entry=0.0001,
        risk_distance=0.001,
        target_r=1.5,
        max_holding_bars=12,
        block_reason="spread consumes too much of stop distance",
        max_risk_approved=False,
        status=PaperTradeStatus.STOP,
        exit_at=signal_at + timedelta(minutes=45),
        exit_price=1.1020,
        result_r=-1.0,
        bars_held=3,
    )
    (tmp_path / "EURUSD_failed_auction_blocked_probes.jsonl").write_text(
        probe.model_dump_json() + "\n",
        encoding="utf-8",
    )

    bars = []
    base = NOW - timedelta(hours=8)
    for i in range(100):
        at = base + timedelta(minutes=5 * i)
        px = 1.1000 + i * 0.00002
        bars.append(bar(at, px, px + 0.0003, px - 0.0002, px + 0.00005))
    monkeypatch.setattr(
        "app.services.trading_intelligence.load_recent_closed_market_bars",
        lambda *args, **kwargs: bars,
    )

    overview = build_trading_intelligence(
        Path("/unused"),
        tmp_path,
        now=NOW,
        window_hours=12,
        symbols=("EURUSD",),
    )

    assert len(overview.trades) == 2
    asset = overview.assets[0]
    assert asset.symbol == "EURUSD"
    assert asset.paper_closed_trades == 1
    assert asset.paper_total_r == 1.8
    assert asset.blocked_closed_probes == 1
    assert asset.blocked_total_r == -1.0
    assert overview.limitations


def test_market_opportunity_counts_prebirth_signal_as_captured() -> None:
    start = NOW.replace(hour=8, minute=0)
    bars = []
    for i in range(30):
        at = start + timedelta(minutes=5 * i)
        close = 1.1000 + (0.00003 * i)
        bars.append(bar(at, close, close + 0.0002, close - 0.0002, close))
    for i in range(15, 24):
        b = bars[i]
        bars[i] = b.model_copy(
            update={
                "close": b.close + 0.0020,
                "high": b.high + 0.0022,
            }
        )

    birth_at = bars[13].timestamp + timedelta(minutes=5)
    early_signal = diagnostic(
        at=birth_at - timedelta(minutes=10),
        side=Side.BUY,
        state=ShadowSignalState.SIGNAL_EXECUTABLE,
    )

    episodes = _market_opportunity_episodes(
        symbol="EURUSD",
        bars=bars,
        signals=[early_signal],
        window_start=start,
        window_end=NOW,
        threshold_atr=1.5,
        horizon_bars=12,
    )

    assert episodes
    assert episodes[0].capture_state == OpportunityCaptureState.EXECUTABLE
