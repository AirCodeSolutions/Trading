from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.causal_precursor import CausalPrecursorObservation
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
    AdmittedTradeEarlyContextReport,
    AdmittedTradeEarlyContextSummary,
    BlockedProbeEarlyContextReport,
    BlockedProbeEarlyContextSummary,
    MarketOpportunityEpisode,
    OpportunityCaptureState,
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityDetectionStage,
    OpportunityWaitingSummary,
    ProbeEarlyContextReport,
    ProbeEarlyContextSummary,
    TradeIntelligence,
    WaitingEarlyContextReport,
    WaitingEarlyContextSummary,
)
from app.domain.xau_microbar import XauMicrobarM1
from app.services.trading_intelligence import (
    _build_admitted_trade_early_context_report,
    _build_blocked_probe_early_context_report,
    _build_probe_early_context_report,
    _build_waiting_early_context_report,
    _candidate_evidence_coverage,
    _market_opportunity_episodes,
    _side_aligned_imbalance,
    _side_aligned_move_r,
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


def test_waiting_early_context_uses_only_closed_m1_and_pre_signal_precursor(
    tmp_path: Path,
) -> None:
    target_signal = NOW.replace(hour=10, minute=20)
    early_signal = NOW.replace(hour=11, minute=0)
    microbars: list[XauMicrobarM1] = []

    def microbar(
        minute_at: datetime,
        *,
        mid_open: float,
        mid_close: float,
        up: int,
        down: int,
    ) -> XauMicrobarM1:
        spread = 0.0002
        bid_open = mid_open - spread / 2
        bid_close = mid_close - spread / 2
        ask_open = mid_open + spread / 2
        ask_close = mid_close + spread / 2
        return XauMicrobarM1(
            minute_at=minute_at,
            first_quote_at=minute_at,
            last_quote_at=minute_at + timedelta(seconds=50),
            bid_open=bid_open,
            bid_high=max(bid_open, bid_close),
            bid_low=min(bid_open, bid_close),
            bid_close=bid_close,
            ask_open=ask_open,
            ask_high=max(ask_open, ask_close),
            ask_low=min(ask_open, ask_close),
            ask_close=ask_close,
            mid_open=mid_open,
            mid_high=max(mid_open, mid_close),
            mid_low=min(mid_open, mid_close),
            mid_close=mid_close,
            spread_open=spread,
            spread_high=spread,
            spread_low=spread,
            spread_close=spread,
            spread_sum=spread * (up + down + 1),
            quote_count=up + down + 1,
            mid_up_ticks=up,
            mid_down_ticks=down,
        )

    for index in range(15):
        minute = target_signal - timedelta(minutes=15 - index)
        microbars.append(
            microbar(
                minute,
                mid_open=100.0 + index * 0.05,
                mid_close=100.03 + index * 0.05,
                up=3,
                down=1,
            )
        )
    # This bar closes after target_signal and must not leak into the geometry.
    microbars.append(
        microbar(
            target_signal,
            mid_open=101.0,
            mid_close=100.0,
            up=0,
            down=20,
        )
    )
    for index in range(15):
        minute = early_signal - timedelta(minutes=15 - index)
        microbars.append(
            microbar(
                minute,
                mid_open=102.0 - index * 0.02,
                mid_close=101.98 - index * 0.02,
                up=1,
                down=3,
            )
        )

    ledger = tmp_path / "BTCUSD_micro_m1.jsonl"
    ledger.write_text(
        "".join(row.model_dump_json() + "\n" for row in microbars),
        encoding="utf-8",
    )

    target = MarketOpportunityEpisode(
        episode_id="target",
        symbol="BTCUSD",
        side=Side.BUY,
        birth_at=target_signal - timedelta(minutes=5),
        horizon_end_at=target_signal + timedelta(minutes=55),
        reference_price=100.0,
        atr_m5=1.0,
        move_atr=3.0,
        capture_state=OpportunityCaptureState.BLOCKED,
        first_signal_at=target_signal,
        first_signal_state=ShadowSignalState.SIGNAL_BLOCKED,
        first_signal_strategy_id="BTCUSD:directional_transition",
        first_signal_mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        first_signal_price=100.9,
        signal_lead_lag_minutes=5.0,
        move_consumed_at_signal_atr=0.9,
        move_remaining_after_signal_atr=2.1,
        move_consumed_fraction=0.30,
    )
    early = target.model_copy(
        update={
            "episode_id": "early",
            "birth_at": early_signal - timedelta(minutes=5),
            "horizon_end_at": early_signal + timedelta(minutes=55),
            "first_signal_at": early_signal,
            "first_signal_price": 102.1,
            "move_consumed_at_signal_atr": 0.2,
            "move_remaining_after_signal_atr": 2.8,
            "move_consumed_fraction": 0.10,
        }
    )
    precursor_before = CausalPrecursorObservation(
        symbol="BTCUSD",
        first_seen_at=target_signal - timedelta(minutes=10),
        latest_closed_m5_at=target_signal - timedelta(minutes=15),
        pattern=OpportunityCausalPattern.COMPRESSION_BREAKOUT,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.COMPRESSION_BREAKOUT,
            side=Side.BUY,
        ),
    )
    precursor_after = precursor_before.model_copy(
        update={
            "first_seen_at": early_signal + timedelta(minutes=1),
            "latest_closed_m5_at": early_signal,
        }
    )

    report = _build_waiting_early_context_report(
        opportunities=[target, early],
        precursors=[precursor_before, precursor_after],
        runtime_dir=tmp_path,
        now=NOW,
        window_hours=168,
    )

    assert report.waiting_episodes == 2
    assert report.m1_eligible_episodes == 2
    assert report.tick_pressure_eligible_episodes == 2
    assert report.target_band_episodes == 1
    assert report.target_band_m1_eligible_episodes == 1
    assert report.target_band_tick_pressure_eligible_episodes == 1
    assert report.target_band_with_precursor == 1
    assert report.m1_coverage_started_at["BTCUSD"] == microbars[0].minute_at

    summary = report.summaries[0]
    assert summary.strategy_id == "BTCUSD:directional_transition"
    assert summary.tick_pressure_eligible_episodes == 2
    assert summary.early_reaction_m1_episodes == 1
    assert summary.target_band_m1_episodes == 1
    assert summary.target_band_tick_pressure_episodes == 1
    assert summary.target_band_with_precursor == 1
    assert summary.target_band_precursor_rate == 1.0
    assert summary.median_target_side_aligned_tick_imbalance_5m == 0.5
    assert summary.median_early_side_aligned_tick_imbalance_5m == -0.5
    assert summary.target_minus_early_tick_imbalance_5m == 1.0

    target_row = next(
        row for row in report.recent_m1_episodes if row.episode_id == "target"
    )
    early_row = next(
        row for row in report.recent_m1_episodes if row.episode_id == "early"
    )
    assert target_row.directional_tick_samples_5m == 20
    assert target_row.side_aligned_tick_imbalance_5m == 0.5
    assert target_row.precursor_first_seen_at == precursor_before.first_seen_at
    assert target_row.precursor_lead_minutes_to_signal == 10.0
    assert early_row.precursor_first_seen_at is None


def test_side_aligned_tick_imbalance_flips_sell_direction() -> None:
    assert _side_aligned_imbalance(Side.BUY, 0.25) == 0.25
    assert _side_aligned_imbalance(Side.SELL, -0.25) == 0.25
    assert _side_aligned_imbalance(Side.SELL, 0.25) == -0.25
    assert _side_aligned_imbalance(Side.BUY, None) is None


def test_probe_early_context_separates_winners_and_losses(
    tmp_path: Path,
) -> None:
    signal_win = NOW.replace(hour=9, minute=30)
    signal_loss = NOW.replace(hour=10, minute=30)

    def microbar(
        minute_at: datetime,
        *,
        up: int,
        down: int,
    ) -> XauMicrobarM1:
        spread = 0.0002
        return XauMicrobarM1(
            minute_at=minute_at,
            first_quote_at=minute_at,
            last_quote_at=minute_at + timedelta(seconds=50),
            bid_open=1.0,
            bid_high=1.001,
            bid_low=0.999,
            bid_close=1.0,
            ask_open=1.0002,
            ask_high=1.0012,
            ask_low=0.9992,
            ask_close=1.0002,
            mid_open=1.0001,
            mid_high=1.0011,
            mid_low=0.9991,
            mid_close=1.0001,
            spread_open=spread,
            spread_high=spread,
            spread_low=spread,
            spread_close=spread,
            spread_sum=spread * (up + down + 1),
            quote_count=up + down + 1,
            mid_up_ticks=up,
            mid_down_ticks=down,
        )

    rows: list[XauMicrobarM1] = []
    for signal_at, up, down in (
        (signal_win, 4, 1),
        (signal_loss, 3, 2),
    ):
        for index in range(15):
            rows.append(
                microbar(
                    signal_at - timedelta(minutes=15 - index),
                    up=up,
                    down=down,
                )
            )
    (tmp_path / "BTCUSD_micro_m1.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )

    def probe(
        trade_id: str,
        signal_at: datetime,
        result_r: float,
    ) -> ShadowPaperTrade:
        return ShadowPaperTrade(
            trade_id=trade_id,
            symbol="BTCUSD",
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=Side.BUY,
            signal_at=signal_at,
            entry_bar_at=signal_at,
            opened_at=signal_at,
            entry_price=100.0,
            stop_price=99.0,
            target_price=101.8,
            spread_at_entry=0.1,
            lots=0.01,
            risk_eur=10.0,
            risk_distance=1.0,
            target_r=1.8,
            max_holding_bars=12,
            status=(
                PaperTradeStatus.TARGET
                if result_r > 0
                else PaperTradeStatus.STOP
            ),
            exit_at=signal_at + timedelta(minutes=10),
            exit_price=101.8 if result_r > 0 else 99.0,
            result_r=result_r,
            pnl_eur=result_r * 10.0,
            bars_held=2,
        )

    precursor = CausalPrecursorObservation(
        symbol="BTCUSD",
        first_seen_at=signal_win - timedelta(minutes=5),
        latest_closed_m5_at=signal_win - timedelta(minutes=5),
        pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.BUY,
        ),
    )

    report = _build_probe_early_context_report(
        probes=[
            probe("win", signal_win, 1.8),
            probe("loss", signal_loss, -1.0),
        ],
        precursors=[precursor],
        runtime_dir=tmp_path,
        now=NOW,
        window_hours=168,
    )

    assert report.resolved_probes == 2
    assert report.m1_eligible_probes == 2
    assert report.tick_pressure_eligible_probes == 2
    assert report.tick_pressure_wins == 1
    assert report.tick_pressure_losses == 1
    summary = report.summaries[0]
    assert summary.tick_pressure_wins == 1
    assert summary.tick_pressure_losses == 1
    assert summary.tick_pressure_total_r == 0.8
    assert summary.tick_pressure_expectancy_r == 0.4
    assert summary.winner_median_side_aligned_tick_imbalance_5m == 0.6
    assert summary.loser_median_side_aligned_tick_imbalance_5m == 0.2
    assert abs(summary.winner_minus_loser_tick_imbalance_5m - 0.4) < 1e-12
    assert summary.winner_pressure_agreement_rate == 1.0
    assert summary.loser_pressure_agreement_rate == 1.0
    assert summary.winner_median_spread_to_risk == 0.1
    assert summary.loser_median_spread_to_risk == 0.1
    assert summary.winner_median_path_efficiency_5m == 0.0
    assert summary.loser_median_path_efficiency_5m == 0.0
    assert summary.winner_precursor_rate == 1.0
    assert summary.loser_precursor_rate == 0.0
    assert summary.winner_precursor_patterns == {"directional_displacement": 1}
    assert summary.loser_precursor_patterns == {}


def test_blocked_probe_early_context_groups_exact_block_reason(
    tmp_path: Path,
) -> None:
    signal_win = NOW.replace(hour=8, minute=30)
    signal_loss = NOW.replace(hour=9, minute=30)
    signal_other = NOW.replace(hour=10, minute=30)

    def microbar(
        minute_at: datetime,
        *,
        up: int,
        down: int,
    ) -> XauMicrobarM1:
        spread = 0.0002
        return XauMicrobarM1(
            minute_at=minute_at,
            first_quote_at=minute_at,
            last_quote_at=minute_at + timedelta(seconds=50),
            bid_open=1.0,
            bid_high=1.001,
            bid_low=0.999,
            bid_close=1.0,
            ask_open=1.0002,
            ask_high=1.0012,
            ask_low=0.9992,
            ask_close=1.0002,
            mid_open=1.0001,
            mid_high=1.0011,
            mid_low=0.9991,
            mid_close=1.0001,
            spread_open=spread,
            spread_high=spread,
            spread_low=spread,
            spread_close=spread,
            spread_sum=spread * (up + down + 1),
            quote_count=up + down + 1,
            mid_up_ticks=up,
            mid_down_ticks=down,
        )

    microbars: list[XauMicrobarM1] = []
    for signal_at, up, down in (
        (signal_win, 4, 1),
        (signal_loss, 2, 3),
        (signal_other, 3, 2),
    ):
        for index in range(15):
            microbars.append(
                microbar(
                    signal_at - timedelta(minutes=15 - index),
                    up=up,
                    down=down,
                )
            )
    (tmp_path / "EURUSD_micro_m1.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in microbars),
        encoding="utf-8",
    )

    def blocked(
        probe_id: str,
        signal_at: datetime,
        result_r: float,
        reason: str,
        spread: float,
    ) -> BlockedOpportunityProbe:
        return BlockedOpportunityProbe(
            probe_id=probe_id,
            symbol="EURUSD",
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=Side.BUY,
            signal_at=signal_at,
            opened_at=signal_at,
            entry_price=1.1,
            stop_price=1.0,
            target_price=1.28,
            spread_at_entry=spread,
            risk_distance=0.1,
            target_r=1.8,
            max_holding_bars=12,
            block_reason=reason,
            max_risk_approved=True,
            status=(
                PaperTradeStatus.TARGET
                if result_r > 0
                else PaperTradeStatus.STOP
            ),
            exit_at=signal_at + timedelta(minutes=10),
            exit_price=1.28 if result_r > 0 else 1.0,
            result_r=result_r,
            bars_held=2,
        )

    spread_reason = "spread consumes too much of the stop distance"
    probes = [
        blocked("spread-win", signal_win, 1.8, spread_reason, 0.03),
        blocked("spread-loss", signal_loss, -1.0, spread_reason, 0.03),
        blocked(
            "lot-loss",
            signal_other,
            -1.0,
            "broker minimum lot exceeds max risk",
            0.01,
        ),
    ]
    precursor = CausalPrecursorObservation(
        symbol="EURUSD",
        first_seen_at=signal_win - timedelta(minutes=5),
        latest_closed_m5_at=signal_win - timedelta(minutes=5),
        pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.BUY,
        ),
    )

    report = _build_blocked_probe_early_context_report(
        probes=probes,
        precursors=[precursor],
        runtime_dir=tmp_path,
        now=NOW,
        window_hours=168,
    )

    assert report.resolved_blocked_probes == 3
    assert report.m1_eligible_probes == 3
    assert report.tick_pressure_eligible_probes == 3
    assert report.tick_pressure_wins == 1
    assert report.tick_pressure_losses == 2
    assert abs(report.tick_pressure_total_r + 0.2) < 1e-12

    by_reason = {row.block_reason: row for row in report.summaries}
    assert set(by_reason) == {
        spread_reason,
        "broker minimum lot exceeds max risk",
    }
    spread = by_reason[spread_reason]
    assert spread.resolved_blocked_probes == 2
    assert spread.m1_eligible_probes == 2
    assert spread.tick_pressure_eligible_probes == 2
    assert spread.wins == 1
    assert spread.losses == 1
    assert abs(spread.total_r - 0.8) < 1e-12
    assert abs(spread.expectancy_r - 0.4) < 1e-12
    assert abs(spread.median_spread_to_risk - 0.3) < 1e-12
    assert abs(spread.median_side_aligned_tick_imbalance_5m - 0.2) < 1e-12
    assert spread.pressure_against_trade_rate == 0.5
    assert spread.pressure_agreement_rate == 1.0
    assert spread.precursor_patterns == {"directional_displacement": 1}


def test_admitted_trade_early_context_compares_follow_through(
    tmp_path: Path,
) -> None:
    signal_win = NOW.replace(hour=9, minute=0)
    signal_loss = NOW.replace(hour=10, minute=0)

    def microbar(
        minute_at: datetime,
        *,
        up: int,
        down: int,
    ) -> XauMicrobarM1:
        spread = 0.0002
        return XauMicrobarM1(
            minute_at=minute_at,
            first_quote_at=minute_at,
            last_quote_at=minute_at + timedelta(seconds=50),
            bid_open=1.0,
            bid_high=1.001,
            bid_low=0.999,
            bid_close=1.0,
            ask_open=1.0002,
            ask_high=1.0012,
            ask_low=0.9992,
            ask_close=1.0002,
            mid_open=1.0001,
            mid_high=1.0011,
            mid_low=0.9991,
            mid_close=1.0001,
            spread_open=spread,
            spread_high=spread,
            spread_low=spread,
            spread_close=spread,
            spread_sum=spread * (up + down + 1),
            quote_count=up + down + 1,
            mid_up_ticks=up,
            mid_down_ticks=down,
        )

    rows: list[XauMicrobarM1] = []
    for signal_at, up, down in (
        (signal_win, 4, 1),
        (signal_loss, 2, 3),
    ):
        for index in range(15):
            rows.append(
                microbar(
                    signal_at - timedelta(minutes=15 - index),
                    up=up,
                    down=down,
                )
            )
    (tmp_path / "BTCUSD_micro_m1.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )

    def paper(
        trade_id: str,
        signal_at: datetime,
        result_r: float,
        spread: float,
    ) -> ShadowPaperTrade:
        return ShadowPaperTrade(
            trade_id=trade_id,
            symbol="BTCUSD",
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=Side.BUY,
            signal_at=signal_at,
            entry_bar_at=signal_at,
            opened_at=signal_at,
            entry_price=100.0,
            stop_price=99.0,
            target_price=101.8,
            spread_at_entry=spread,
            lots=0.01,
            risk_eur=10.0,
            risk_distance=1.0,
            target_r=1.8,
            max_holding_bars=12,
            status=(
                PaperTradeStatus.TARGET
                if result_r > 0
                else PaperTradeStatus.STOP
            ),
            exit_at=signal_at + timedelta(minutes=10),
            exit_price=101.8 if result_r > 0 else 99.0,
            result_r=result_r,
            pnl_eur=result_r * 10.0,
            bars_held=2,
        )

    def intelligence(
        trade_id: str,
        signal_at: datetime,
        result_r: float,
        *,
        mfe_r: float,
        mae_r: float,
        r_wait: float,
    ) -> TradeIntelligence:
        return TradeIntelligence(
            trade_id=trade_id,
            source="paper",
            symbol="BTCUSD",
            mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
            side=Side.BUY,
            signal_at=signal_at,
            opened_at=signal_at,
            exit_at=signal_at + timedelta(minutes=10),
            status="target" if result_r > 0 else "stop",
            entry_price=100.0,
            stop_price=99.0,
            target_price=101.8,
            risk_distance=1.0,
            result_r=result_r,
            pnl_eur=result_r * 10.0,
            mfe_r=mfe_r,
            mae_r=mae_r,
            r_lost_while_waiting=r_wait,
        )

    papers = [
        paper("win", signal_win, 1.8, 0.08),
        paper("loss", signal_loss, -1.0, 0.12),
    ]
    trades = [
        intelligence(
            "win",
            signal_win,
            1.8,
            mfe_r=1.8,
            mae_r=0.2,
            r_wait=0.05,
        ),
        intelligence(
            "loss",
            signal_loss,
            -1.0,
            mfe_r=0.1,
            mae_r=1.0,
            r_wait=0.2,
        ),
    ]
    precursor = CausalPrecursorObservation(
        symbol="BTCUSD",
        first_seen_at=signal_win - timedelta(minutes=5),
        latest_closed_m5_at=signal_win - timedelta(minutes=5),
        pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.BUY,
        ),
    )

    report = _build_admitted_trade_early_context_report(
        trades=trades,
        paper_trades=papers,
        precursors=[precursor],
        runtime_dir=tmp_path,
        now=NOW,
        window_hours=168,
    )

    assert report.resolved_trades == 2
    assert report.m1_eligible_trades == 2
    assert report.tick_pressure_eligible_trades == 2
    assert report.tick_pressure_wins == 1
    assert report.tick_pressure_losses == 1
    assert abs(report.tick_pressure_total_r - 0.8) < 1e-12

    summary = report.summaries[0]
    assert summary.tick_pressure_wins == 1
    assert summary.tick_pressure_losses == 1
    assert summary.winner_median_side_aligned_tick_imbalance_5m == 0.6
    assert summary.loser_median_side_aligned_tick_imbalance_5m == -0.2
    assert summary.winner_median_spread_to_risk == 0.08
    assert summary.loser_median_spread_to_risk == 0.12
    assert summary.winner_median_mfe_r == 1.8
    assert summary.loser_median_mfe_r == 0.1
    assert summary.winner_median_mae_r == 0.2
    assert summary.loser_median_mae_r == 1.0
    assert summary.winner_median_r_lost_while_waiting == 0.05
    assert summary.loser_median_r_lost_while_waiting == 0.2
    assert summary.winner_precursor_rate == 1.0
    assert summary.loser_precursor_rate == 0.0
    assert summary.winner_precursor_patterns == {"directional_displacement": 1}
    assert summary.loser_precursor_patterns == {}


def test_side_aligned_move_r_flips_sell_direction() -> None:
    assert _side_aligned_move_r(Side.BUY, 0.2, 0.1) == 2.0
    assert _side_aligned_move_r(Side.SELL, 0.2, 0.1) == -2.0
    assert _side_aligned_move_r(Side.SELL, -0.2, 0.1) == 2.0
    assert _side_aligned_move_r(Side.BUY, 1.0, 0.0) == 0.0


def test_candidate_evidence_coverage_aggregates_existing_sources() -> None:
    mechanism = OpportunityMechanism.DIRECTIONAL_TRANSITION
    strategy_id = "BTCUSD:directional_transition"

    probe = ProbeEarlyContextReport(
        generated_at=NOW,
        window_hours=168,
        resolved_probes=5,
        m1_eligible_probes=4,
        tick_pressure_eligible_probes=3,
        tick_pressure_wins=2,
        tick_pressure_losses=1,
        summaries=[
            ProbeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol="BTCUSD",
                mechanism=mechanism,
                resolved_probes=5,
                m1_eligible_probes=4,
                tick_pressure_eligible_probes=3,
                tick_pressure_wins=2,
                tick_pressure_losses=1,
                tick_pressure_total_r=2.0,
                tick_pressure_expectancy_r=2.0 / 3.0,
            )
        ],
    )
    waiting = WaitingEarlyContextReport(
        generated_at=NOW,
        window_hours=168,
        target_band_min_fraction=0.25,
        target_band_max_fraction=0.40,
        waiting_episodes=6,
        m1_eligible_episodes=5,
        tick_pressure_eligible_episodes=4,
        target_band_episodes=0,
        target_band_m1_eligible_episodes=0,
        target_band_tick_pressure_eligible_episodes=0,
        target_band_with_precursor=0,
        summaries=[
            WaitingEarlyContextSummary(
                strategy_id=strategy_id,
                symbol="BTCUSD",
                mechanism=mechanism,
                waiting_episodes=6,
                m1_eligible_episodes=5,
                tick_pressure_eligible_episodes=4,
                early_reaction_m1_episodes=0,
                target_band_m1_episodes=0,
                target_band_tick_pressure_episodes=0,
                late_reaction_m1_episodes=0,
                target_band_with_precursor=0,
            )
        ],
    )
    admitted = AdmittedTradeEarlyContextReport(
        generated_at=NOW,
        window_hours=168,
        resolved_trades=2,
        m1_eligible_trades=1,
        tick_pressure_eligible_trades=1,
        tick_pressure_wins=1,
        tick_pressure_losses=0,
        tick_pressure_total_r=1.0,
        summaries=[
            AdmittedTradeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol="BTCUSD",
                mechanism=mechanism,
                resolved_trades=2,
                m1_eligible_trades=1,
                tick_pressure_eligible_trades=1,
                tick_pressure_wins=1,
                tick_pressure_losses=0,
                tick_pressure_total_r=1.0,
                tick_pressure_expectancy_r=1.0,
            )
        ],
    )
    blocked = BlockedProbeEarlyContextReport(
        generated_at=NOW,
        window_hours=168,
        resolved_blocked_probes=5,
        m1_eligible_probes=3,
        tick_pressure_eligible_probes=2,
        tick_pressure_wins=0,
        tick_pressure_losses=2,
        tick_pressure_total_r=-2.0,
        summaries=[
            BlockedProbeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol="BTCUSD",
                mechanism=mechanism,
                block_reason="spread",
                resolved_blocked_probes=3,
                m1_eligible_probes=2,
                tick_pressure_eligible_probes=1,
                wins=0,
                losses=1,
                total_r=-1.0,
                expectancy_r=-1.0,
                median_spread_to_risk=0.2,
                median_path_efficiency_5m=0.3,
            ),
            BlockedProbeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol="BTCUSD",
                mechanism=mechanism,
                block_reason="minimum lot",
                resolved_blocked_probes=2,
                m1_eligible_probes=1,
                tick_pressure_eligible_probes=1,
                wins=0,
                losses=1,
                total_r=-1.0,
                expectancy_r=-1.0,
                median_spread_to_risk=0.1,
                median_path_efficiency_5m=0.4,
            ),
        ],
    )
    waiting_cost = OpportunityWaitingSummary(
        strategy_id=strategy_id,
        symbol="BTCUSD",
        mechanism=mechanism,
        episodes_with_signal=6,
        executable_signals=5,
        blocked_signals=1,
        precursor_then_signal_episodes=3,
        average_signal_lead_lag_minutes=4.0,
        average_move_atr=1.5,
        average_move_consumed_at_signal_atr=0.5,
        average_move_remaining_after_signal_atr=1.0,
        average_move_consumed_fraction=1.0 / 3.0,
        average_precursor_to_signal_minutes=2.0,
    )

    rows = _candidate_evidence_coverage(
        probe_early_context=probe,
        waiting_early_context=waiting,
        admitted_trade_early_context=admitted,
        blocked_probe_early_context=blocked,
        waiting_costs=[waiting_cost],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.strategy_id == strategy_id
    assert row.probe_resolved == 5
    assert row.probe_m1_eligible == 4
    assert row.probe_tick_pressure_eligible == 3
    assert row.probe_m1_coverage_rate == 0.8
    assert row.probe_tick_pressure_coverage_rate == 0.6
    assert row.waiting_episodes == 6
    assert row.waiting_m1_eligible == 5
    assert row.waiting_tick_pressure_eligible == 4
    assert row.admitted_resolved == 2
    assert row.admitted_m1_eligible == 1
    assert row.admitted_tick_pressure_eligible == 1
    assert row.blocked_resolved == 5
    assert row.blocked_m1_eligible == 3
    assert row.blocked_tick_pressure_eligible == 2
    assert row.blocked_m1_coverage_rate == 0.6
    assert row.blocked_tick_pressure_coverage_rate == 0.4


def test_candidate_evidence_coverage_uses_null_rates_without_denominator() -> None:
    rows = _candidate_evidence_coverage(
        probe_early_context=None,
        waiting_early_context=None,
        admitted_trade_early_context=None,
        blocked_probe_early_context=None,
        waiting_costs=[],
    )
    assert rows == []
