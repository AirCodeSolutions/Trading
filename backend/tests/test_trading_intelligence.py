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
from app.domain.trading_intelligence import (
    MarketOpportunityEpisode,
    OpportunityCaptureState,
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityDetectionStage,
)
from app.services.trading_intelligence import (
    _market_opportunity_episodes,
    _trade_metrics,
    _unseen_pattern_summaries,
    _waiting_cost_summaries,
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
    assert episodes[0].first_signal_at == executable_signal.evaluated_at
    assert episodes[0].first_signal_state == ShadowSignalState.SIGNAL_EXECUTABLE
    assert episodes[0].first_signal_strategy_id == "EURUSD:break_retest_reaccel"
    assert episodes[0].first_signal_price == bars[14].close
    assert episodes[0].signal_lead_lag_minutes == 5.0
    assert episodes[0].move_consumed_at_signal_atr is not None
    assert episodes[0].move_remaining_after_signal_atr is not None
    assert episodes[0].move_consumed_fraction is not None

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
    assert episodes[0].first_signal_at == early_signal.evaluated_at
    assert episodes[0].signal_lead_lag_minutes == -10.0
    assert episodes[0].move_consumed_at_signal_atr == 0.0


def test_waiting_cost_summary_groups_first_system_reaction() -> None:
    rows = [
        MarketOpportunityEpisode(
            episode_id="one",
            symbol="BTCUSD",
            side=Side.BUY,
            birth_at=NOW,
            horizon_end_at=NOW + timedelta(hours=1),
            reference_price=100.0,
            atr_m5=1.0,
            move_atr=2.0,
            capture_state=OpportunityCaptureState.EXECUTABLE,
            first_signal_at=NOW + timedelta(minutes=5),
            first_signal_state=ShadowSignalState.SIGNAL_EXECUTABLE,
            first_signal_strategy_id="BTCUSD:directional_transition",
            first_signal_mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            first_signal_price=101.0,
            signal_lead_lag_minutes=5.0,
            move_consumed_at_signal_atr=1.0,
            move_remaining_after_signal_atr=1.0,
            move_consumed_fraction=0.5,
            precursor_to_signal_minutes=10.0,
        ),
        MarketOpportunityEpisode(
            episode_id="two",
            symbol="BTCUSD",
            side=Side.BUY,
            birth_at=NOW + timedelta(hours=2),
            horizon_end_at=NOW + timedelta(hours=3),
            reference_price=110.0,
            atr_m5=1.0,
            move_atr=2.0,
            capture_state=OpportunityCaptureState.BLOCKED,
            first_signal_at=NOW + timedelta(hours=2, minutes=-5),
            first_signal_state=ShadowSignalState.SIGNAL_BLOCKED,
            first_signal_strategy_id="BTCUSD:directional_transition",
            first_signal_mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            first_signal_price=110.5,
            signal_lead_lag_minutes=-5.0,
            move_consumed_at_signal_atr=0.5,
            move_remaining_after_signal_atr=1.5,
            move_consumed_fraction=0.25,
        ),
    ]

    summary = _waiting_cost_summaries(rows)

    assert len(summary) == 1
    item = summary[0]
    assert item.strategy_id == "BTCUSD:directional_transition"
    assert item.episodes_with_signal == 2
    assert item.executable_signals == 1
    assert item.blocked_signals == 1
    assert item.precursor_then_signal_episodes == 1
    assert item.average_signal_lead_lag_minutes == 0.0
    assert item.average_move_atr == 2.0
    assert item.average_move_consumed_at_signal_atr == 0.75
    assert item.average_move_remaining_after_signal_atr == 1.25
    assert item.average_move_consumed_fraction == 0.375
    assert item.average_precursor_to_signal_minutes == 10.0


def test_causal_classifier_detects_upper_auction_failure_reclaim() -> None:
    from app.domain.trading_intelligence import OpportunityCausalPattern
    from app.services.trading_intelligence import _classify_causal_context

    start = NOW.replace(hour=7, minute=0)
    bars = [
        bar(
            start + timedelta(minutes=5 * i),
            1.1000,
            1.1004,
            1.0996,
            1.1000,
        )
        for i in range(30)
    ]
    bars[24] = bar(
        start + timedelta(minutes=5 * 24),
        1.1003,
        1.1010,
        1.0998,
        1.1002,
    )
    atr = [0.001] * len(bars)

    context = _classify_causal_context(
        bars=bars,
        atr=atr,
        index=24,
        episode_side=Side.SELL,
    )

    assert context.pattern == OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM
    assert context.side == Side.SELL
    assert context.aligned_with_move is True
    assert context.sweep_atr > 0.5
    assert context.reclaim_atr > 0
    assert context.evidence == ["upper 24-M5 sweep reclaimed causally"]


def test_causal_classifier_is_independent_of_future_bars() -> None:
    from app.services.trading_intelligence import _classify_causal_context

    start = NOW.replace(hour=7, minute=0)
    bars = [
        bar(
            start + timedelta(minutes=5 * i),
            1.1000,
            1.1004,
            1.0996,
            1.1000,
        )
        for i in range(30)
    ]
    bars[24] = bar(
        start + timedelta(minutes=5 * 24),
        1.1003,
        1.1010,
        1.0998,
        1.1002,
    )
    atr = [0.001] * len(bars)
    original = _classify_causal_context(
        bars=bars,
        atr=atr,
        index=24,
        episode_side=Side.SELL,
    )

    changed = list(bars)
    for i in range(25, len(changed)):
        changed[i] = bar(
            start + timedelta(minutes=5 * i),
            1.5000,
            1.7000,
            1.3000,
            1.6000,
        )
    after_future_change = _classify_causal_context(
        bars=changed,
        atr=atr,
        index=24,
        episode_side=Side.SELL,
    )

    assert after_future_change == original


def test_causal_pattern_summary_counts_alignment_and_misses() -> None:
    from app.domain.trading_intelligence import (
        MarketOpportunityEpisode,
        OpportunityCausalContext,
        OpportunityCausalPattern,
    )
    from app.services.trading_intelligence import _causal_pattern_summaries

    rows = [
        MarketOpportunityEpisode(
            episode_id="one",
            symbol="BTCUSD",
            side=Side.BUY,
            birth_at=NOW,
            horizon_end_at=NOW + timedelta(hours=1),
            reference_price=100.0,
            atr_m5=1.0,
            move_atr=2.0,
            capture_state=OpportunityCaptureState.MISSED,
            causal_context=OpportunityCausalContext(
                pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
                side=Side.BUY,
                aligned_with_move=True,
            ),
        ),
        MarketOpportunityEpisode(
            episode_id="two",
            symbol="BTCUSD",
            side=Side.SELL,
            birth_at=NOW + timedelta(hours=1),
            horizon_end_at=NOW + timedelta(hours=2),
            reference_price=101.0,
            atr_m5=1.0,
            move_atr=3.0,
            capture_state=OpportunityCaptureState.BLOCKED,
            causal_context=OpportunityCausalContext(
                pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
                side=Side.BUY,
                aligned_with_move=False,
            ),
        ),
    ]

    summary = _causal_pattern_summaries(rows)

    assert len(summary) == 1
    assert summary[0].episodes == 2
    assert summary[0].missed == 1
    assert summary[0].aligned == 1
    assert summary[0].opposed == 1
    assert summary[0].no_direction == 0
    assert summary[0].average_move_atr == 2.5


def test_unseen_pattern_summaries_are_prospective_pattern_radar() -> None:
    def episode(
        *,
        episode_id: str,
        symbol: str,
        side: Side,
        pattern: OpportunityCausalPattern,
        aligned: bool | None,
        move_atr: float,
        return_6_atr: float,
        compression: float,
        stage: OpportunityDetectionStage = OpportunityDetectionStage.UNSEEN,
    ) -> MarketOpportunityEpisode:
        return MarketOpportunityEpisode(
            episode_id=episode_id,
            symbol=symbol,
            side=side,
            birth_at=NOW - timedelta(minutes=30),
            horizon_end_at=NOW + timedelta(minutes=30),
            reference_price=100.0,
            atr_m5=1.0,
            move_atr=move_atr,
            capture_state=OpportunityCaptureState.MISSED,
            detection_stage=stage,
            causal_context=OpportunityCausalContext(
                pattern=pattern,
                side=(Side.SELL if aligned is False else side) if aligned is not None else None,
                aligned_with_move=aligned,
                return_6_atr=return_6_atr,
                compression_6_24=compression,
            ),
        )

    rows = [
        episode(
            episode_id="a",
            symbol="XAUUSD",
            side=Side.BUY,
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            aligned=False,
            move_atr=2.0,
            return_6_atr=-2.0,
            compression=0.4,
        ),
        episode(
            episode_id="b",
            symbol="BTCUSD",
            side=Side.SELL,
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            aligned=True,
            move_atr=3.0,
            return_6_atr=1.0,
            compression=0.6,
        ),
        episode(
            episode_id="c",
            symbol="XAUUSD",
            side=Side.SELL,
            pattern=OpportunityCausalPattern.UNCLASSIFIED,
            aligned=None,
            move_atr=4.0,
            return_6_atr=0.5,
            compression=0.5,
        ),
        episode(
            episode_id="ignored",
            symbol="XAUUSD",
            side=Side.BUY,
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            aligned=False,
            move_atr=9.0,
            return_6_atr=9.0,
            compression=0.9,
            stage=OpportunityDetectionStage.PRECURSOR_ONLY,
        ),
    ]

    result = _unseen_pattern_summaries(rows)

    assert [row.pattern for row in result] == [
        OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        OpportunityCausalPattern.UNCLASSIFIED,
    ]
    displacement = result[0]
    assert displacement.episodes == 2
    assert displacement.buy_episodes == 1
    assert displacement.sell_episodes == 1
    assert displacement.symbols == {"BTCUSD": 1, "XAUUSD": 1}
    assert displacement.average_move_atr == 2.5
    assert displacement.opposed_context_rate == 0.5
    assert displacement.neutral_context_rate == 0.0
    assert displacement.average_abs_return_6_atr == 1.5
    assert displacement.average_compression_6_24 == 0.5

    neutral = result[1]
    assert neutral.episodes == 1
    assert neutral.neutral_context_rate == 1.0
