from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean, median

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    AdmittedTradeEarlyContextEpisode,
    AdmittedTradeEarlyContextReport,
    AdmittedTradeEarlyContextSummary,
    AssetIntelligence,
    BlockedProbeEarlyContextEpisode,
    BlockedProbeEarlyContextReport,
    BlockedProbeEarlyContextSummary,
    MarketOpportunityEpisode,
    OpportunityCaptureState,
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityCausalPatternSummary,
    OpportunityDetectionStage,
    OpportunityWaitingSummary,
    ProbeEarlyContextEpisode,
    ProbeEarlyContextReport,
    ProbeEarlyContextSummary,
    TradeIntelligence,
    TradingIntelligenceOverview,
    UnseenOpportunityPatternSummary,
    WaitingEarlyContextEpisode,
    WaitingEarlyContextReport,
    WaitingEarlyContextSummary,
)
from app.domain.xau_microbar import XauMicrobarM1
from app.services.blocked_probe import load_blocked_probe_state, load_closed_probes
from app.services.causal_precursor import (
    load_causal_precursor_collection_state,
    load_causal_precursors,
)
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.shadow_paper import load_closed_trades, load_shadow_paper_state
from app.services.xau_microbar import (
    _geometry_window,
    load_xau_microbars,
    microbar_ledger_file,
)

DEFAULT_WINDOW_HOURS = 48
MARKET_MOVE_THRESHOLD_ATR = 1.5
MARKET_MOVE_HORIZON_BARS = 12
SIGNAL_CAPTURE_WINDOW_BARS = 3
WAITING_TARGET_MIN_CONSUMED_FRACTION = 0.25
WAITING_TARGET_MAX_CONSUMED_FRACTION = 0.40


def build_trading_intelligence(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    symbols: tuple[str, ...] | None = None,
    market_move_threshold_atr: float = MARKET_MOVE_THRESHOLD_ATR,
    market_move_horizon_bars: int = MARKET_MOVE_HORIZON_BARS,
    include_waiting_early_context: bool = False,
) -> TradingIntelligenceOverview:
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")
    if market_move_threshold_atr <= 0:
        raise ValueError("market_move_threshold_atr must be positive")
    if market_move_horizon_bars <= 0:
        raise ValueError("market_move_horizon_bars must be positive")

    window_start = now - timedelta(hours=window_hours)
    allowed = tuple(symbol.upper() for symbol in symbols) if symbols else None
    signal_rows = _load_signal_rows(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=set(allowed) if allowed else None,
    )
    precursor_state = load_causal_precursor_collection_state(runtime_dir)
    precursor_rows = load_causal_precursors(
        runtime_dir,
        window_start=window_start
        - timedelta(minutes=5 * SIGNAL_CAPTURE_WINDOW_BARS),
        window_end=now,
        symbols=allowed,
    )

    paper_trades = _load_paper_trades(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=set(allowed) if allowed else None,
    )
    probes = _load_blocked_probes(
        runtime_dir,
        window_start=window_start,
        window_end=now,
        allowed=set(allowed) if allowed else None,
    )

    discovered_symbols = {
        trade.symbol.upper() for trade in paper_trades
    } | {
        probe.symbol.upper() for probe in probes
    } | {
        row.symbol.upper() for row in signal_rows
    }
    if allowed:
        discovered_symbols.update(allowed)

    bars_by_symbol: dict[str, list[MarketBar]] = {}
    recent_bar_limit = max(
        100,
        window_hours * 12 + market_move_horizon_bars + 64,
    )
    for symbol in sorted(discovered_symbols):
        bars_by_symbol[symbol] = load_recent_closed_market_bars(
            files_dir,
            symbol,
            Timeframe.M5,
            now,
            limit=recent_bar_limit,
        )

    trade_rows = [
        _paper_trade_intelligence(trade, bars_by_symbol.get(trade.symbol.upper(), []))
        for trade in paper_trades
    ]
    trade_rows.extend(
        _blocked_probe_intelligence(probe, bars_by_symbol.get(probe.symbol.upper(), []))
        for probe in probes
    )
    trade_rows.sort(key=lambda row: row.signal_at, reverse=True)

    signals_by_symbol: dict[str, list[ShadowOpportunityDiagnostic]] = defaultdict(list)
    for row in signal_rows:
        signals_by_symbol[row.symbol.upper()].append(row)
    for rows in signals_by_symbol.values():
        rows.sort(key=lambda row: row.evaluated_at)

    precursors_by_symbol: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in precursor_rows:
        precursors_by_symbol[row.symbol.upper()].append(row)
    for rows in precursors_by_symbol.values():
        rows.sort(key=lambda row: row.first_seen_at)

    opportunities: list[MarketOpportunityEpisode] = []
    for symbol, bars in bars_by_symbol.items():
        opportunities.extend(
            _market_opportunity_episodes(
                symbol=symbol,
                bars=bars,
                signals=signals_by_symbol.get(symbol, []),
                precursors=precursors_by_symbol.get(symbol, []),
                window_start=window_start,
                window_end=now,
                threshold_atr=market_move_threshold_atr,
                horizon_bars=market_move_horizon_bars,
            )
        )
    opportunities.sort(key=lambda row: row.birth_at, reverse=True)

    precursor_started_at = (
        precursor_state.started_at if precursor_state is not None else None
    )
    precursor_eligible = [
        row
        for row in opportunities
        if precursor_started_at is not None
        and row.birth_at >= precursor_started_at
    ]
    precursor_seen = [
        row
        for row in precursor_eligible
        if row.precursor_first_seen_at is not None
    ]
    precursor_leads = [
        row.precursor_lead_minutes
        for row in precursor_seen
        if row.precursor_lead_minutes is not None
    ]
    precursor_only = sum(
        row.detection_stage == OpportunityDetectionStage.PRECURSOR_ONLY
        for row in precursor_eligible
    )
    precursor_unseen = sum(
        row.detection_stage == OpportunityDetectionStage.UNSEEN
        for row in precursor_eligible
    )
    precursor_signal_blocked = sum(
        row.detection_stage == OpportunityDetectionStage.SIGNAL_BLOCKED
        and row.precursor_first_seen_at is not None
        for row in precursor_eligible
    )
    precursor_signal_executable = sum(
        row.detection_stage == OpportunityDetectionStage.SIGNAL_EXECUTABLE
        and row.precursor_first_seen_at is not None
        for row in precursor_eligible
    )
    signal_without_precursor = sum(
        row.capture_state != OpportunityCaptureState.MISSED
        and row.precursor_first_seen_at is None
        for row in precursor_eligible
    )
    converted_from_precursor = (
        precursor_signal_blocked + precursor_signal_executable
    )

    assets = _asset_summaries(
        symbols=sorted(discovered_symbols),
        trades=trade_rows,
        opportunities=opportunities,
    )
    causal_patterns = _causal_pattern_summaries(opportunities)
    unseen_patterns = _unseen_pattern_summaries(precursor_eligible)
    waiting_costs = _waiting_cost_summaries(opportunities)
    waiting_early_context = (
        _build_waiting_early_context_report(
            opportunities=opportunities,
            precursors=precursor_rows,
            runtime_dir=runtime_dir,
            now=now,
            window_hours=window_hours,
        )
        if include_waiting_early_context
        else None
    )
    blocked_probe_early_context = (
        _build_blocked_probe_early_context_report(
            probes=[
                probe
                for probe in probes
                if probe.result_r is not None
            ],
            precursors=precursor_rows,
            runtime_dir=runtime_dir,
            now=now,
            window_hours=window_hours,
        )
        if include_waiting_early_context
        else None
    )
    admitted_trade_early_context = (
        _build_admitted_trade_early_context_report(
            trades=[row for row in trade_rows if row.source == "paper"],
            paper_trades=paper_trades,
            precursors=precursor_rows,
            runtime_dir=runtime_dir,
            now=now,
            window_hours=window_hours,
        )
        if include_waiting_early_context
        else None
    )
    probe_early_context = (
        _build_probe_early_context_report(
            probes=_load_unqualified_probe_trades(
                runtime_dir,
                window_start=window_start,
                window_end=now,
                allowed=set(allowed) if allowed else None,
            ),
            precursors=precursor_rows,
            runtime_dir=runtime_dir,
            now=now,
            window_hours=window_hours,
        )
        if include_waiting_early_context
        else None
    )
    return TradingIntelligenceOverview(
        generated_at=now,
        window_hours=window_hours,
        window_start=window_start,
        window_end=now,
        market_move_threshold_atr=market_move_threshold_atr,
        market_move_horizon_bars=market_move_horizon_bars,
        precursor_collection_started_at=precursor_started_at,
        precursor_eligible_opportunities=len(precursor_eligible),
        precursor_seen_opportunities=len(precursor_seen),
        precursor_seen_rate=(
            len(precursor_seen) / len(precursor_eligible)
            if precursor_eligible
            else 0.0
        ),
        precursor_only_opportunities=precursor_only,
        precursor_unseen_opportunities=precursor_unseen,
        precursor_signal_blocked_opportunities=precursor_signal_blocked,
        precursor_signal_executable_opportunities=precursor_signal_executable,
        signal_without_precursor_opportunities=signal_without_precursor,
        precursor_to_signal_conversion_rate=(
            converted_from_precursor / len(precursor_seen)
            if precursor_seen
            else 0.0
        ),
        average_precursor_lead_minutes=(
            fmean(precursor_leads) if precursor_leads else 0.0
        ),
        trades=trade_rows[:100],
        opportunities=opportunities[:200],
        assets=assets,
        causal_patterns=causal_patterns,
        unseen_patterns=unseen_patterns,
        waiting_costs=waiting_costs,
        waiting_early_context=waiting_early_context,
        probe_early_context=probe_early_context,
        blocked_probe_early_context=blocked_probe_early_context,
        admitted_trade_early_context=admitted_trade_early_context,
        limitations=[
            (
                "Market opportunities are a retrospective research denominator: "
                "a 1.5 ATR M5 move inside the next 12 M5 bars, deduplicated by horizon."
            ),
            (
                "Causal precursor first_seen is prospective-only and starts at "
                "the deployed collector timestamp; no historical first_seen is backfilled."
            ),
            (
                "MFE/MAE are reconstructed from M5 OHLC bars; intrabar path ordering "
                "cannot be recovered."
            ),
            (
                "Causal-pattern labels use only bars available by episode birth. "
                "Pattern alignment with the later move is retrospective research metadata."
            ),
            (
                "Waiting-cost signal timestamps and prices are causal, but consumed/remaining "
                "move metrics are measured against the retrospective market-opportunity horizon "
                "and are research-only."
            ),
        ],
    )


def _load_signal_rows(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[ShadowOpportunityDiagnostic]:
    rows: list[ShadowOpportunityDiagnostic] = []
    for path in sorted(runtime_dir.glob("*.jsonl")):
        if (
            path.name.endswith("_paper_trades.jsonl")
            or path.name.endswith("_blocked_probes.jsonl")
            or path.name == "execution_costs.jsonl"
        ):
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = ShadowOpportunityDiagnostic.model_validate_json(line)
                except ValueError:
                    continue
                if allowed is not None and row.symbol.upper() not in allowed:
                    continue
                if window_start <= row.evaluated_at <= window_end:
                    rows.append(row)
    return rows


def _load_paper_trades(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_paper_trades.jsonl")):
        for trade in load_closed_trades(path):
            if allowed is not None and trade.symbol.upper() not in allowed:
                continue
            if window_start <= trade.signal_at <= window_end:
                rows.append(trade)
    for path in sorted(runtime_dir.glob("*_paper_state.json")):
        trade = load_shadow_paper_state(path).open_trade
        if trade is None:
            continue
        if allowed is not None and trade.symbol.upper() not in allowed:
            continue
        if window_start <= trade.signal_at <= window_end:
            rows.append(trade)
    return rows


def _load_blocked_probes(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[BlockedOpportunityProbe]:
    rows: list[BlockedOpportunityProbe] = []
    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for probe in load_closed_probes(path):
            if allowed is not None and probe.symbol.upper() not in allowed:
                continue
            if window_start <= probe.signal_at <= window_end:
                rows.append(probe)
    for path in sorted(runtime_dir.glob("*_blocked_probe_state.json")):
        probe = load_blocked_probe_state(path).open_probe
        if probe is None:
            continue
        if allowed is not None and probe.symbol.upper() not in allowed:
            continue
        if window_start <= probe.signal_at <= window_end:
            rows.append(probe)
    return rows


def _load_unqualified_probe_trades(
    runtime_dir: Path,
    *,
    window_start: datetime,
    window_end: datetime,
    allowed: set[str] | None,
) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        for probe in load_closed_trades(path):
            if probe.result_r is None:
                continue
            if allowed is not None and probe.symbol.upper() not in allowed:
                continue
            if window_start <= probe.signal_at <= window_end:
                rows.append(probe)
    return rows


def _paper_trade_intelligence(
    trade: ShadowPaperTrade,
    bars: list[MarketBar],
) -> TradeIntelligence:
    metrics = _trade_metrics(
        side=trade.side,
        signal_at=trade.signal_at,
        opened_at=trade.opened_at,
        exit_at=trade.exit_at,
        entry_price=trade.entry_price,
        stop_price=trade.stop_price,
        target_price=trade.target_price,
        risk_distance=trade.risk_distance,
        spread=trade.spread_at_entry,
        bars=bars,
    )
    return TradeIntelligence(
        trade_id=trade.trade_id,
        source="paper",
        symbol=trade.symbol,
        mechanism=trade.mechanism,
        side=trade.side,
        signal_at=trade.signal_at,
        opened_at=trade.opened_at,
        exit_at=trade.exit_at,
        status=trade.status.value,
        entry_price=trade.entry_price,
        stop_price=trade.stop_price,
        target_price=trade.target_price,
        risk_distance=trade.risk_distance,
        result_r=trade.result_r,
        pnl_eur=trade.pnl_eur,
        **metrics,
    )


def _blocked_probe_intelligence(
    probe: BlockedOpportunityProbe,
    bars: list[MarketBar],
) -> TradeIntelligence:
    metrics = _trade_metrics(
        side=probe.side,
        signal_at=probe.signal_at,
        opened_at=probe.opened_at,
        exit_at=probe.exit_at,
        entry_price=probe.entry_price,
        stop_price=probe.stop_price,
        target_price=probe.target_price,
        risk_distance=probe.risk_distance,
        spread=probe.spread_at_entry,
        bars=bars,
    )
    return TradeIntelligence(
        trade_id=probe.probe_id,
        source="blocked_probe",
        symbol=probe.symbol,
        mechanism=probe.mechanism,
        side=probe.side,
        signal_at=probe.signal_at,
        opened_at=probe.opened_at,
        exit_at=probe.exit_at,
        status=probe.status.value,
        entry_price=probe.entry_price,
        stop_price=probe.stop_price,
        target_price=probe.target_price,
        risk_distance=probe.risk_distance,
        result_r=probe.result_r,
        block_reason=probe.block_reason,
        **metrics,
    )


def _trade_metrics(
    *,
    side: Side,
    signal_at: datetime,
    opened_at: datetime,
    exit_at: datetime | None,
    entry_price: float,
    stop_price: float,
    target_price: float,
    risk_distance: float,
    spread: float,
    bars: list[MarketBar],
) -> dict[str, float | int | None]:
    signal_bar = next((bar for bar in bars if bar.timestamp >= signal_at), None)
    signal_entry_price: float | None = None
    rr_at_signal: float | None = None
    r_lost = 0.0
    if signal_bar is not None:
        signal_entry_price = (
            signal_bar.open + spread if side == Side.BUY else signal_bar.open
        )
        r_lost = (
            (entry_price - signal_entry_price) / risk_distance
            if side == Side.BUY
            else (signal_entry_price - entry_price) / risk_distance
        )
        rr_at_signal = _reward_risk(
            side=side,
            entry=signal_entry_price,
            stop=stop_price,
            target=target_price,
        )

    rr_at_entry = _reward_risk(
        side=side,
        entry=entry_price,
        stop=stop_price,
        target=target_price,
    )
    first_full_bar = _next_full_m5_bar_start(opened_at)
    end_at = exit_at or (bars[-1].timestamp + timedelta(minutes=5) if bars else opened_at)
    trade_bars = [
        bar
        for bar in bars
        if first_full_bar <= bar.timestamp and bar.timestamp <= end_at
    ]

    mfe_r = 0.0
    mae_r = 0.0
    time_to_mfe: int | None = None
    for bar in trade_bars:
        if side == Side.BUY:
            favorable = max(0.0, bar.high - entry_price)
            adverse = max(0.0, entry_price - bar.low)
        else:
            favorable = max(0.0, entry_price - (bar.low + spread))
            adverse = max(0.0, (bar.high + spread) - entry_price)
        current_mfe = favorable / risk_distance
        if current_mfe > mfe_r:
            mfe_r = current_mfe
            close_at = bar.timestamp + timedelta(minutes=5)
            time_to_mfe = max(0, int((close_at - opened_at).total_seconds() // 60))
        mae_r = max(mae_r, adverse / risk_distance)

    mfe_before_entry = 0.0
    if signal_entry_price is not None:
        pre_entry_bars = [
            bar
            for bar in bars
            if signal_at <= bar.timestamp
            and bar.timestamp + timedelta(minutes=5) <= opened_at
        ]
        for bar in pre_entry_bars:
            if side == Side.BUY:
                favorable = max(0.0, bar.high - signal_entry_price)
            else:
                favorable = max(0.0, signal_entry_price - (bar.low + spread))
            mfe_before_entry = max(mfe_before_entry, favorable / risk_distance)

    return {
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "time_to_mfe_minutes": time_to_mfe,
        "signal_entry_price": signal_entry_price,
        "entry_delay_seconds": max(0.0, (opened_at - signal_at).total_seconds()),
        "r_lost_while_waiting": r_lost,
        "rr_at_signal": rr_at_signal,
        "rr_at_entry": rr_at_entry,
        "mfe_consumed_before_entry_r": mfe_before_entry,
    }


def _reward_risk(
    *,
    side: Side,
    entry: float,
    stop: float,
    target: float,
) -> float | None:
    if side == Side.BUY:
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _next_full_m5_bar_start(at: datetime) -> datetime:
    minute_floor = at.replace(second=0, microsecond=0)
    remainder = minute_floor.minute % 5
    if remainder == 0 and at.second == 0 and at.microsecond == 0:
        return minute_floor
    minutes = 5 - remainder if remainder else 5
    return minute_floor + timedelta(minutes=minutes)



def _classify_causal_context(
    *,
    bars: list[MarketBar],
    atr: list[float],
    index: int,
    episode_side: Side,
) -> OpportunityCausalContext:
    if index < 3 or index >= len(bars) or index >= len(atr):
        return OpportunityCausalContext()

    bar = bars[index]
    current_atr = atr[index]
    if current_atr <= 0:
        return OpportunityCausalContext()

    bar_range = bar.high - bar.low
    body_fraction = (
        (bar.close - bar.open) / bar_range if bar_range > 0 else 0.0
    )
    return_3_atr = (bar.close - bars[index - 3].close) / current_atr
    return_6_atr = (
        (bar.close - bars[index - 6].close) / current_atr
        if index >= 6
        else 0.0
    )

    prior_24 = bars[index - 24 : index] if index >= 24 else bars[:index]
    prior_6 = bars[index - 6 : index] if index >= 6 else bars[:index]
    if not prior_24:
        return OpportunityCausalContext(
            return_3_atr=return_3_atr,
            return_6_atr=return_6_atr,
            body_fraction=body_fraction,
        )

    prior_high = max(item.high for item in prior_24)
    prior_low = min(item.low for item in prior_24)
    range_24 = prior_high - prior_low
    raw_position = (
        (bar.close - prior_low) / range_24 if range_24 > 0 else 0.5
    )
    range_position_24 = min(1.0, max(0.0, raw_position))

    compression_6_24 = 1.0
    if prior_6 and range_24 > 0:
        range_6 = max(item.high for item in prior_6) - min(
            item.low for item in prior_6
        )
        compression_6_24 = max(0.0, range_6 / range_24)

    pattern = OpportunityCausalPattern.UNCLASSIFIED
    pattern_side: Side | None = None
    sweep_atr = 0.0
    reclaim_atr = 0.0
    evidence: list[str] = []

    upper_wick = (
        bar.high - max(bar.open, bar.close) if bar_range > 0 else 0.0
    )
    lower_wick = (
        min(bar.open, bar.close) - bar.low if bar_range > 0 else 0.0
    )
    close_location = (
        (bar.close - bar.low) / bar_range if bar_range > 0 else 0.5
    )

    if index >= 24 and bar_range > 0:
        if (
            bar.high > prior_high + 0.10 * current_atr
            and bar.close < prior_high - 0.02 * current_atr
            and upper_wick / bar_range >= 0.35
            and close_location <= 0.50
        ):
            pattern = OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM
            pattern_side = Side.SELL
            sweep_atr = (bar.high - prior_high) / current_atr
            reclaim_atr = (prior_high - bar.close) / current_atr
            evidence.append("upper 24-M5 sweep reclaimed causally")
        elif (
            bar.low < prior_low - 0.10 * current_atr
            and bar.close > prior_low + 0.02 * current_atr
            and lower_wick / bar_range >= 0.35
            and close_location >= 0.50
        ):
            pattern = OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM
            pattern_side = Side.BUY
            sweep_atr = (prior_low - bar.low) / current_atr
            reclaim_atr = (bar.close - prior_low) / current_atr
            evidence.append("lower 24-M5 sweep reclaimed causally")

    if (
        pattern == OpportunityCausalPattern.UNCLASSIFIED
        and index >= 24
        and len(prior_6) >= 6
        and compression_6_24 <= 0.35
        and bar_range > 0
    ):
        prior_6_high = max(item.high for item in prior_6)
        prior_6_low = min(item.low for item in prior_6)
        if bar.close > prior_6_high and body_fraction >= 0.50:
            pattern = OpportunityCausalPattern.COMPRESSION_BREAKOUT
            pattern_side = Side.BUY
            evidence.append("6/24-M5 compression released upward")
        elif bar.close < prior_6_low and body_fraction <= -0.50:
            pattern = OpportunityCausalPattern.COMPRESSION_BREAKOUT
            pattern_side = Side.SELL
            evidence.append("6/24-M5 compression released downward")

    if pattern == OpportunityCausalPattern.UNCLASSIFIED:
        if return_3_atr >= 0.50 and body_fraction >= 0.50:
            pattern = OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT
            pattern_side = Side.BUY
            evidence.append("3-M5 bullish displacement")
        elif return_3_atr <= -0.50 and body_fraction <= -0.50:
            pattern = OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT
            pattern_side = Side.SELL
            evidence.append("3-M5 bearish displacement")

    if pattern == OpportunityCausalPattern.UNCLASSIFIED and index >= 24:
        if range_position_24 >= 0.80 and return_6_atr >= 1.0:
            pattern = OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH
            pattern_side = Side.BUY
            evidence.append("upper structural extreme after bullish stretch")
        elif range_position_24 <= 0.20 and return_6_atr <= -1.0:
            pattern = OpportunityCausalPattern.STRUCTURAL_EXTREME_STRETCH
            pattern_side = Side.SELL
            evidence.append("lower structural extreme after bearish stretch")

    if (
        pattern == OpportunityCausalPattern.UNCLASSIFIED
        and index >= 24
        and compression_6_24 <= 0.35
    ):
        pattern = OpportunityCausalPattern.COMPRESSION_STATE
        evidence.append("6/24-M5 compression state")

    if (
        pattern == OpportunityCausalPattern.UNCLASSIFIED
        and index >= 24
        and (range_position_24 >= 0.80 or range_position_24 <= 0.20)
    ):
        pattern = OpportunityCausalPattern.STRUCTURAL_EXTREME
        evidence.append("price at 24-M5 structural extreme")

    aligned = pattern_side == episode_side if pattern_side is not None else None
    return OpportunityCausalContext(
        pattern=pattern,
        side=pattern_side,
        aligned_with_move=aligned,
        range_position_24=range_position_24,
        return_3_atr=return_3_atr,
        return_6_atr=return_6_atr,
        compression_6_24=compression_6_24,
        body_fraction=body_fraction,
        sweep_atr=max(0.0, sweep_atr),
        reclaim_atr=max(0.0, reclaim_atr),
        evidence=evidence,
    )


def _market_opportunity_episodes(
    *,
    symbol: str,
    bars: list[MarketBar],
    signals: list[ShadowOpportunityDiagnostic],
    precursors: list[CausalPrecursorObservation] | None = None,
    window_start: datetime,
    window_end: datetime,
    threshold_atr: float,
    horizon_bars: int,
) -> list[MarketOpportunityEpisode]:
    if len(bars) < 14 + horizon_bars + 1:
        return []
    atr = _atr_series(bars)
    episodes: list[MarketOpportunityEpisode] = []
    index = 13
    last_index = len(bars) - horizon_bars - 1
    while index <= last_index:
        bar = bars[index]
        birth_at = bar.timestamp + timedelta(minutes=5)
        if birth_at < window_start:
            index += 1
            continue
        if birth_at > window_end:
            break
        current_atr = atr[index]
        if current_atr <= 0:
            index += 1
            continue

        future = bars[index + 1 : index + 1 + horizon_bars]
        up_move = max(item.high for item in future) - bar.close
        down_move = bar.close - min(item.low for item in future)
        up_atr = max(0.0, up_move / current_atr)
        down_atr = max(0.0, down_move / current_atr)
        move_atr = max(up_atr, down_atr)
        if move_atr < threshold_atr:
            index += 1
            continue

        side = Side.BUY if up_atr >= down_atr else Side.SELL
        capture_window_start = birth_at - timedelta(
            minutes=5 * SIGNAL_CAPTURE_WINDOW_BARS
        )
        capture_window_end = birth_at + timedelta(
            minutes=5 * SIGNAL_CAPTURE_WINDOW_BARS
        )
        matches = [
            row
            for row in signals
            if row.side == side
            and row.state != ShadowSignalState.NO_SIGNAL
            and capture_window_start
            <= row.latest_closed_m5_at + timedelta(minutes=5)
            <= capture_window_end
        ]
        executable = [
            row for row in matches if row.state == ShadowSignalState.SIGNAL_EXECUTABLE
        ]
        blocked = [
            row for row in matches if row.state == ShadowSignalState.SIGNAL_BLOCKED
        ]
        if executable:
            capture_state = OpportunityCaptureState.EXECUTABLE
        elif blocked:
            capture_state = OpportunityCaptureState.BLOCKED
        else:
            capture_state = OpportunityCaptureState.MISSED

        strategies = sorted(
            {f"{row.symbol}:{row.mechanism.value}" for row in matches}
        )
        first_signal = (
            min(
                matches,
                key=lambda row: (
                    row.evaluated_at,
                    row.mechanism.value,
                    row.state.value,
                ),
            )
            if matches
            else None
        )
        first_signal_price = (
            _closed_bar_price(bars, first_signal.latest_closed_m5_at)
            if first_signal is not None
            else None
        )
        signal_lead_lag_minutes = (
            (first_signal.evaluated_at - birth_at).total_seconds() / 60.0
            if first_signal is not None
            else None
        )
        move_consumed_at_signal_atr = (
            0.0
            if first_signal_price is not None
            and signal_lead_lag_minutes is not None
            and signal_lead_lag_minutes <= 0
            else (
                _aligned_move_atr(
                    side=side,
                    reference_price=bar.close,
                    observed_price=first_signal_price,
                    atr=current_atr,
                )
                if first_signal_price is not None
                else None
            )
        )
        move_remaining_after_signal_atr = (
            max(0.0, move_atr - move_consumed_at_signal_atr)
            if move_consumed_at_signal_atr is not None
            else None
        )
        move_consumed_fraction = (
            min(1.0, move_consumed_at_signal_atr / move_atr)
            if move_consumed_at_signal_atr is not None and move_atr > 0
            else None
        )
        aligned_precursors = [
            row
            for row in (precursors or [])
            if row.side == side
            and capture_window_start <= row.first_seen_at <= birth_at
        ]
        earliest_precursor = (
            min(aligned_precursors, key=lambda row: row.first_seen_at)
            if aligned_precursors
            else None
        )
        if capture_state == OpportunityCaptureState.EXECUTABLE:
            detection_stage = OpportunityDetectionStage.SIGNAL_EXECUTABLE
        elif capture_state == OpportunityCaptureState.BLOCKED:
            detection_stage = OpportunityDetectionStage.SIGNAL_BLOCKED
        elif earliest_precursor is not None:
            detection_stage = OpportunityDetectionStage.PRECURSOR_ONLY
        else:
            detection_stage = OpportunityDetectionStage.UNSEEN

        precursor_to_signal_minutes = (
            (first_signal.evaluated_at - earliest_precursor.first_seen_at).total_seconds()
            / 60.0
            if first_signal is not None
            and earliest_precursor is not None
            and first_signal.evaluated_at >= earliest_precursor.first_seen_at
            else None
        )

        causal_context = _classify_causal_context(
            bars=bars,
            atr=atr,
            index=index,
            episode_side=side,
        )
        episodes.append(
            MarketOpportunityEpisode(
                episode_id=f"{symbol}-{birth_at.isoformat()}-{side.value}",
                symbol=symbol,
                side=side,
                birth_at=birth_at,
                horizon_end_at=future[-1].timestamp + timedelta(minutes=5),
                reference_price=bar.close,
                atr_m5=current_atr,
                move_atr=move_atr,
                capture_state=capture_state,
                detection_stage=detection_stage,
                matching_strategies=strategies,
                first_signal_at=(
                    first_signal.evaluated_at if first_signal is not None else None
                ),
                first_signal_state=(
                    first_signal.state if first_signal is not None else None
                ),
                first_signal_strategy_id=(
                    f"{first_signal.symbol}:{first_signal.mechanism.value}"
                    if first_signal is not None
                    else None
                ),
                first_signal_mechanism=(
                    first_signal.mechanism if first_signal is not None else None
                ),
                first_signal_price=first_signal_price,
                signal_lead_lag_minutes=signal_lead_lag_minutes,
                move_consumed_at_signal_atr=move_consumed_at_signal_atr,
                move_remaining_after_signal_atr=move_remaining_after_signal_atr,
                move_consumed_fraction=move_consumed_fraction,
                precursor_first_seen_at=(
                    earliest_precursor.first_seen_at
                    if earliest_precursor is not None
                    else None
                ),
                precursor_pattern=(
                    earliest_precursor.pattern
                    if earliest_precursor is not None
                    else None
                ),
                precursor_lead_minutes=(
                    (birth_at - earliest_precursor.first_seen_at).total_seconds()
                    / 60.0
                    if earliest_precursor is not None
                    else None
                ),
                precursor_observations=len(aligned_precursors),
                precursor_to_signal_minutes=precursor_to_signal_minutes,
                causal_context=causal_context,
            )
        )
        index += horizon_bars
    return episodes


def _closed_bar_price(
    bars: list[MarketBar],
    timestamp: datetime,
) -> float | None:
    for bar in bars:
        if bar.timestamp == timestamp:
            return bar.close
    return None


def _aligned_move_atr(
    *,
    side: Side,
    reference_price: float,
    observed_price: float,
    atr: float,
) -> float:
    if atr <= 0:
        return 0.0
    distance = (
        observed_price - reference_price
        if side == Side.BUY
        else reference_price - observed_price
    )
    return max(0.0, distance / atr)


def _waiting_cost_summaries(
    opportunities: list[MarketOpportunityEpisode],
) -> list[OpportunityWaitingSummary]:
    grouped: dict[str, list[MarketOpportunityEpisode]] = defaultdict(list)
    for row in opportunities:
        if (
            row.first_signal_strategy_id is None
            or row.first_signal_mechanism is None
            or row.first_signal_state is None
            or row.signal_lead_lag_minutes is None
            or row.move_consumed_at_signal_atr is None
            or row.move_remaining_after_signal_atr is None
            or row.move_consumed_fraction is None
        ):
            continue
        grouped[row.first_signal_strategy_id].append(row)

    output: list[OpportunityWaitingSummary] = []
    for strategy_id, rows in grouped.items():
        precursor_delays = [
            row.precursor_to_signal_minutes
            for row in rows
            if row.precursor_to_signal_minutes is not None
        ]
        first = rows[0]
        output.append(
            OpportunityWaitingSummary(
                strategy_id=strategy_id,
                symbol=first.symbol,
                mechanism=first.first_signal_mechanism,
                episodes_with_signal=len(rows),
                executable_signals=sum(
                    row.first_signal_state == ShadowSignalState.SIGNAL_EXECUTABLE
                    for row in rows
                ),
                blocked_signals=sum(
                    row.first_signal_state == ShadowSignalState.SIGNAL_BLOCKED
                    for row in rows
                ),
                precursor_then_signal_episodes=len(precursor_delays),
                average_signal_lead_lag_minutes=fmean(
                    row.signal_lead_lag_minutes
                    for row in rows
                    if row.signal_lead_lag_minutes is not None
                ),
                average_move_atr=fmean(row.move_atr for row in rows),
                average_move_consumed_at_signal_atr=fmean(
                    row.move_consumed_at_signal_atr
                    for row in rows
                    if row.move_consumed_at_signal_atr is not None
                ),
                average_move_remaining_after_signal_atr=fmean(
                    row.move_remaining_after_signal_atr
                    for row in rows
                    if row.move_remaining_after_signal_atr is not None
                ),
                average_move_consumed_fraction=fmean(
                    row.move_consumed_fraction
                    for row in rows
                    if row.move_consumed_fraction is not None
                ),
                average_precursor_to_signal_minutes=(
                    fmean(precursor_delays) if precursor_delays else 0.0
                ),
            )
        )

    return sorted(
        output,
        key=lambda row: (
            -row.episodes_with_signal,
            -row.average_move_consumed_fraction,
            row.strategy_id,
        ),
    )


def _build_admitted_trade_early_context_report(
    *,
    trades: list[TradeIntelligence],
    paper_trades: list[ShadowPaperTrade],
    precursors: list[CausalPrecursorObservation],
    runtime_dir: Path,
    now: datetime,
    window_hours: int,
) -> AdmittedTradeEarlyContextReport:
    resolved = [
        row for row in trades
        if row.result_r is not None
    ]
    paper_by_id = {row.trade_id: row for row in paper_trades}
    symbols = sorted({row.symbol.upper() for row in resolved})
    microbars_by_symbol = {
        symbol: load_xau_microbars(runtime_dir / microbar_ledger_file(symbol))
        for symbol in symbols
    }
    precursors_by_symbol: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in precursors:
        precursors_by_symbol[row.symbol.upper()].append(row)
    for rows in precursors_by_symbol.values():
        rows.sort(key=lambda item: item.first_seen_at)

    episodes: list[AdmittedTradeEarlyContextEpisode] = []
    for trade in resolved:
        source = paper_by_id.get(trade.trade_id)
        if source is None:
            continue
        microbars = _microbars_closed_before(
            microbars_by_symbol.get(trade.symbol.upper(), []),
            trade.signal_at,
            minutes=15,
        )
        geometry_5m = _geometry_window(microbars, 5) if microbars else None
        geometry_15m = _geometry_window(microbars, 15) if microbars else None
        if geometry_5m is None:
            continue
        imbalance_5m = _side_aligned_imbalance(
            trade.side,
            geometry_5m.mid_tick_imbalance,
        )
        imbalance_15m = (
            _side_aligned_imbalance(
                trade.side,
                geometry_15m.mid_tick_imbalance,
            )
            if geometry_15m is not None
            else None
        )
        precursor = _latest_matching_precursor_before_signal(
            precursors_by_symbol.get(trade.symbol.upper(), []),
            side=trade.side,
            signal_at=trade.signal_at,
        )
        episodes.append(
            AdmittedTradeEarlyContextEpisode(
                trade_id=trade.trade_id,
                strategy_id=f"{trade.symbol}:{trade.mechanism.value}",
                symbol=trade.symbol,
                mechanism=trade.mechanism,
                side=trade.side,
                signal_at=trade.signal_at,
                status=trade.status,
                result_r=trade.result_r,
                mfe_r=trade.mfe_r,
                mae_r=trade.mae_r,
                r_lost_while_waiting=trade.r_lost_while_waiting,
                spread_to_risk=source.spread_at_entry / source.risk_distance,
                directional_tick_samples_5m=geometry_5m.directional_tick_samples,
                side_aligned_tick_imbalance_5m=imbalance_5m,
                side_aligned_tick_imbalance_15m=imbalance_15m,
                pressure_agreement_5m_15m=_pressure_agreement(
                    imbalance_5m,
                    imbalance_15m,
                ),
                path_efficiency_5m=geometry_5m.path_efficiency,
                precursor_pattern=(
                    precursor.pattern if precursor is not None else None
                ),
            )
        )

    resolved_counts = Counter(
        f"{row.symbol}:{row.mechanism.value}" for row in resolved
    )
    grouped: dict[str, list[AdmittedTradeEarlyContextEpisode]] = defaultdict(list)
    for row in episodes:
        grouped[row.strategy_id].append(row)

    summaries: list[AdmittedTradeEarlyContextSummary] = []
    for strategy_id, eligible in grouped.items():
        tick = [
            row for row in eligible
            if row.side_aligned_tick_imbalance_5m is not None
        ]
        wins = [row for row in tick if row.result_r > 0]
        losses = [row for row in tick if row.result_r < 0]
        win_agreement = [
            row.pressure_agreement_5m_15m for row in wins
            if row.pressure_agreement_5m_15m is not None
        ]
        loss_agreement = [
            row.pressure_agreement_5m_15m for row in losses
            if row.pressure_agreement_5m_15m is not None
        ]
        first = eligible[0]
        summaries.append(
            AdmittedTradeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol=first.symbol,
                mechanism=first.mechanism,
                resolved_trades=resolved_counts[strategy_id],
                m1_eligible_trades=len(eligible),
                tick_pressure_eligible_trades=len(tick),
                tick_pressure_wins=len(wins),
                tick_pressure_losses=len(losses),
                tick_pressure_total_r=sum(row.result_r for row in tick),
                tick_pressure_expectancy_r=(
                    fmean(row.result_r for row in tick) if tick else 0.0
                ),
                winner_median_side_aligned_tick_imbalance_5m=_median_or_none(
                    row.side_aligned_tick_imbalance_5m for row in wins
                ),
                loser_median_side_aligned_tick_imbalance_5m=_median_or_none(
                    row.side_aligned_tick_imbalance_5m for row in losses
                ),
                winner_pressure_agreement_rate=_bool_rate_or_none(win_agreement),
                loser_pressure_agreement_rate=_bool_rate_or_none(loss_agreement),
                winner_median_spread_to_risk=_median_or_none(
                    row.spread_to_risk for row in wins
                ),
                loser_median_spread_to_risk=_median_or_none(
                    row.spread_to_risk for row in losses
                ),
                winner_median_mfe_r=_median_or_none(row.mfe_r for row in wins),
                loser_median_mfe_r=_median_or_none(row.mfe_r for row in losses),
                winner_median_mae_r=_median_or_none(row.mae_r for row in wins),
                loser_median_mae_r=_median_or_none(row.mae_r for row in losses),
                winner_median_r_lost_while_waiting=_median_or_none(
                    row.r_lost_while_waiting for row in wins
                ),
                loser_median_r_lost_while_waiting=_median_or_none(
                    row.r_lost_while_waiting for row in losses
                ),
                winner_precursor_rate=_precursor_rate(wins),
                loser_precursor_rate=_precursor_rate(losses),
                winner_precursor_patterns=_precursor_pattern_counts(wins),
                loser_precursor_patterns=_precursor_pattern_counts(losses),
            )
        )

    tick_all = [
        row for row in episodes
        if row.side_aligned_tick_imbalance_5m is not None
    ]
    return AdmittedTradeEarlyContextReport(
        generated_at=now,
        window_hours=window_hours,
        resolved_trades=len(resolved),
        m1_eligible_trades=len(episodes),
        tick_pressure_eligible_trades=len(tick_all),
        tick_pressure_wins=sum(row.result_r > 0 for row in tick_all),
        tick_pressure_losses=sum(row.result_r < 0 for row in tick_all),
        tick_pressure_total_r=sum(row.result_r for row in tick_all),
        summaries=sorted(
            summaries,
            key=lambda row: (
                -row.tick_pressure_eligible_trades,
                -row.m1_eligible_trades,
                row.strategy_id,
            ),
        ),
        recent_tick_pressure_trades=sorted(
            tick_all,
            key=lambda row: row.signal_at,
            reverse=True,
        )[:100],
        limitations=[
            (
                "This report contains admitted PAPER outcomes only; probes and "
                "blocked replays remain separate."
            ),
            (
                "M1 geometry uses only microbars fully closed before signal_at "
                "and is never backfilled before directional tick collection."
            ),
            (
                "Winner/loser differences are descriptive until both classes "
                "contain enough genuinely post-deployment observations."
            ),
        ],
    )


def _median_or_none(values: Iterable[float | None]) -> float | None:
    rows = [value for value in values if value is not None]
    return median(rows) if rows else None


def _bool_rate_or_none(values: Iterable[bool]) -> float | None:
    rows = list(values)
    return sum(rows) / len(rows) if rows else None


def _precursor_rate(
    rows: list[AdmittedTradeEarlyContextEpisode],
) -> float | None:
    if not rows:
        return None
    return sum(row.precursor_pattern is not None for row in rows) / len(rows)


def _precursor_pattern_counts(
    rows: list[AdmittedTradeEarlyContextEpisode],
) -> dict[str, int]:
    return dict(
        Counter(
            row.precursor_pattern.value
            for row in rows
            if row.precursor_pattern is not None
        )
    )


def _build_blocked_probe_early_context_report(
    *,
    probes: list[BlockedOpportunityProbe],
    precursors: list[CausalPrecursorObservation],
    runtime_dir: Path,
    now: datetime,
    window_hours: int,
) -> BlockedProbeEarlyContextReport:
    symbols = sorted({row.symbol.upper() for row in probes})
    microbars_by_symbol = {
        symbol: load_xau_microbars(runtime_dir / microbar_ledger_file(symbol))
        for symbol in symbols
    }
    precursors_by_symbol: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in precursors:
        precursors_by_symbol[row.symbol.upper()].append(row)
    for rows in precursors_by_symbol.values():
        rows.sort(key=lambda item: item.first_seen_at)

    episodes: list[BlockedProbeEarlyContextEpisode] = []
    for probe in probes:
        if probe.result_r is None:
            continue
        microbars = _microbars_closed_before(
            microbars_by_symbol.get(probe.symbol.upper(), []),
            probe.signal_at,
            minutes=15,
        )
        geometry_5m = _geometry_window(microbars, 5) if microbars else None
        geometry_15m = _geometry_window(microbars, 15) if microbars else None
        if geometry_5m is None:
            continue
        imbalance_5m = _side_aligned_imbalance(
            probe.side,
            geometry_5m.mid_tick_imbalance,
        )
        imbalance_15m = (
            _side_aligned_imbalance(
                probe.side,
                geometry_15m.mid_tick_imbalance,
            )
            if geometry_15m is not None
            else None
        )
        precursor = _latest_matching_precursor_before_signal(
            precursors_by_symbol.get(probe.symbol.upper(), []),
            side=probe.side,
            signal_at=probe.signal_at,
        )
        episodes.append(
            BlockedProbeEarlyContextEpisode(
                probe_id=probe.probe_id,
                strategy_id=f"{probe.symbol}:{probe.mechanism.value}",
                symbol=probe.symbol,
                mechanism=probe.mechanism,
                side=probe.side,
                signal_at=probe.signal_at,
                block_reason=probe.block_reason,
                result_r=probe.result_r,
                spread_to_risk=probe.spread_at_entry / probe.risk_distance,
                directional_tick_samples_5m=geometry_5m.directional_tick_samples,
                side_aligned_tick_imbalance_5m=imbalance_5m,
                side_aligned_tick_imbalance_15m=imbalance_15m,
                pressure_agreement_5m_15m=_pressure_agreement(
                    imbalance_5m,
                    imbalance_15m,
                ),
                path_efficiency_5m=geometry_5m.path_efficiency,
                precursor_pattern=(
                    precursor.pattern if precursor is not None else None
                ),
            )
        )

    resolved_counts = Counter(
        (
            f"{probe.symbol}:{probe.mechanism.value}",
            probe.block_reason,
        )
        for probe in probes
        if probe.result_r is not None
    )
    grouped: dict[
        tuple[str, str], list[BlockedProbeEarlyContextEpisode]
    ] = defaultdict(list)
    for row in episodes:
        grouped[(row.strategy_id, row.block_reason)].append(row)

    summaries: list[BlockedProbeEarlyContextSummary] = []
    for (strategy_id, block_reason), eligible in grouped.items():
        tick = [
            row
            for row in eligible
            if row.side_aligned_tick_imbalance_5m is not None
        ]
        imbalances_5m = _nonnull(
            row.side_aligned_tick_imbalance_5m for row in tick
        )
        agreements = [
            row.pressure_agreement_5m_15m
            for row in tick
            if row.pressure_agreement_5m_15m is not None
        ]
        first = eligible[0]
        summaries.append(
            BlockedProbeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol=first.symbol,
                mechanism=first.mechanism,
                block_reason=block_reason,
                resolved_blocked_probes=resolved_counts[
                    (strategy_id, block_reason)
                ],
                m1_eligible_probes=len(eligible),
                tick_pressure_eligible_probes=len(tick),
                wins=sum(row.result_r > 0 for row in tick),
                losses=sum(row.result_r < 0 for row in tick),
                total_r=sum(row.result_r for row in tick),
                expectancy_r=(
                    fmean(row.result_r for row in tick)
                    if tick
                    else 0.0
                ),
                median_spread_to_risk=(
                    median(row.spread_to_risk for row in tick)
                    if tick
                    else median(row.spread_to_risk for row in eligible)
                ),
                median_side_aligned_tick_imbalance_5m=(
                    median(imbalances_5m) if imbalances_5m else None
                ),
                pressure_against_trade_rate=(
                    sum(value < 0 for value in imbalances_5m)
                    / len(imbalances_5m)
                    if imbalances_5m
                    else None
                ),
                pressure_agreement_rate=(
                    sum(agreements) / len(agreements)
                    if agreements
                    else None
                ),
                median_path_efficiency_5m=median(
                    row.path_efficiency_5m for row in eligible
                ),
                precursor_patterns=dict(
                    Counter(
                        row.precursor_pattern.value
                        for row in eligible
                        if row.precursor_pattern is not None
                    )
                ),
            )
        )

    tick_all = [
        row for row in episodes if row.side_aligned_tick_imbalance_5m is not None
    ]
    return BlockedProbeEarlyContextReport(
        generated_at=now,
        window_hours=window_hours,
        resolved_blocked_probes=sum(
            probe.result_r is not None for probe in probes
        ),
        m1_eligible_probes=len(episodes),
        tick_pressure_eligible_probes=len(tick_all),
        tick_pressure_wins=sum(row.result_r > 0 for row in tick_all),
        tick_pressure_losses=sum(row.result_r < 0 for row in tick_all),
        tick_pressure_total_r=sum(row.result_r for row in tick_all),
        summaries=sorted(
            summaries,
            key=lambda row: (
                -row.tick_pressure_eligible_probes,
                -row.m1_eligible_probes,
                row.symbol,
                row.strategy_id,
                row.block_reason,
            ),
        ),
        recent_tick_pressure_probes=sorted(
            tick_all,
            key=lambda row: row.signal_at,
            reverse=True,
        )[:100],
        limitations=[
            (
                "Blocked-probe outcomes are counterfactual research replays and are "
                "grouped by the exact runtime block reason."
            ),
            (
                "M1 geometry uses only microbars fully closed before signal_at and "
                "is never backfilled before directional tick collection existed."
            ),
            (
                "A blocked-probe winner does not imply the guard should be relaxed; "
                "guard changes require robust reason-specific economic evidence."
            ),
        ],
    )


def _build_probe_early_context_report(
    *,
    probes: list[ShadowPaperTrade],
    precursors: list[CausalPrecursorObservation],
    runtime_dir: Path,
    now: datetime,
    window_hours: int,
) -> ProbeEarlyContextReport:
    symbols = sorted({row.symbol.upper() for row in probes})
    microbars_by_symbol = {
        symbol: load_xau_microbars(runtime_dir / microbar_ledger_file(symbol))
        for symbol in symbols
    }
    precursors_by_symbol: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in precursors:
        precursors_by_symbol[row.symbol.upper()].append(row)
    for rows in precursors_by_symbol.values():
        rows.sort(key=lambda item: item.first_seen_at)

    episodes: list[ProbeEarlyContextEpisode] = []
    for probe in probes:
        microbars = _microbars_closed_before(
            microbars_by_symbol.get(probe.symbol.upper(), []),
            probe.signal_at,
            minutes=15,
        )
        geometry_5m = _geometry_window(microbars, 5) if microbars else None
        geometry_15m = _geometry_window(microbars, 15) if microbars else None
        if geometry_5m is None:
            continue
        precursor = _latest_matching_precursor_before_signal(
            precursors_by_symbol.get(probe.symbol.upper(), []),
            side=probe.side,
            signal_at=probe.signal_at,
        )
        episodes.append(
            ProbeEarlyContextEpisode(
                trade_id=probe.trade_id,
                strategy_id=f"{probe.symbol}:{probe.mechanism.value}",
                symbol=probe.symbol,
                mechanism=probe.mechanism,
                side=probe.side,
                signal_at=probe.signal_at,
                status=probe.status.value,
                result_r=probe.result_r or 0.0,
                directional_tick_samples_5m=geometry_5m.directional_tick_samples,
                side_aligned_tick_imbalance_5m=_side_aligned_imbalance(
                    probe.side,
                    geometry_5m.mid_tick_imbalance,
                ),
                directional_tick_samples_15m=(
                    geometry_15m.directional_tick_samples
                    if geometry_15m is not None
                    else 0
                ),
                side_aligned_tick_imbalance_15m=(
                    _side_aligned_imbalance(
                        probe.side,
                        geometry_15m.mid_tick_imbalance,
                    )
                    if geometry_15m is not None
                    else None
                ),
                pressure_agreement_5m_15m=_pressure_agreement(
                    _side_aligned_imbalance(
                        probe.side,
                        geometry_5m.mid_tick_imbalance,
                    ),
                    (
                        _side_aligned_imbalance(
                            probe.side,
                            geometry_15m.mid_tick_imbalance,
                        )
                        if geometry_15m is not None
                        else None
                    ),
                ),
                spread_to_risk=(
                    probe.spread_at_entry / probe.risk_distance
                    if probe.risk_distance > 0
                    else 0.0
                ),
                average_quotes_per_bar_5m=geometry_5m.average_quotes_per_bar,
                path_efficiency_5m=geometry_5m.path_efficiency,
                precursor_first_seen_at=(
                    precursor.first_seen_at if precursor is not None else None
                ),
                precursor_pattern=(
                    precursor.pattern if precursor is not None else None
                ),
                precursor_lead_minutes_to_signal=(
                    (probe.signal_at - precursor.first_seen_at).total_seconds()
                    / 60.0
                    if precursor is not None
                    else None
                ),
            )
        )

    grouped: dict[str, list[ProbeEarlyContextEpisode]] = defaultdict(list)
    for row in episodes:
        grouped[row.strategy_id].append(row)
    resolved_counts = Counter(
        f"{probe.symbol}:{probe.mechanism.value}" for probe in probes
    )

    summaries: list[ProbeEarlyContextSummary] = []
    for strategy_id, eligible in grouped.items():
        tick = [
            row
            for row in eligible
            if row.side_aligned_tick_imbalance_5m is not None
        ]
        wins = [row for row in tick if row.result_r > 0]
        losses = [row for row in tick if row.result_r < 0]
        win_5m = _nonnull(row.side_aligned_tick_imbalance_5m for row in wins)
        loss_5m = _nonnull(row.side_aligned_tick_imbalance_5m for row in losses)
        win_15m = _nonnull(row.side_aligned_tick_imbalance_15m for row in wins)
        loss_15m = _nonnull(row.side_aligned_tick_imbalance_15m for row in losses)
        winner_median_5m = median(win_5m) if win_5m else None
        loser_median_5m = median(loss_5m) if loss_5m else None
        winner_agreement = [
            row.pressure_agreement_5m_15m
            for row in wins
            if row.pressure_agreement_5m_15m is not None
        ]
        loser_agreement = [
            row.pressure_agreement_5m_15m
            for row in losses
            if row.pressure_agreement_5m_15m is not None
        ]
        first = eligible[0]
        summaries.append(
            ProbeEarlyContextSummary(
                strategy_id=strategy_id,
                symbol=first.symbol,
                mechanism=first.mechanism,
                resolved_probes=resolved_counts[strategy_id],
                m1_eligible_probes=len(eligible),
                tick_pressure_eligible_probes=len(tick),
                tick_pressure_wins=len(wins),
                tick_pressure_losses=len(losses),
                tick_pressure_total_r=sum(row.result_r for row in tick),
                tick_pressure_expectancy_r=(
                    fmean(row.result_r for row in tick) if tick else 0.0
                ),
                winner_median_side_aligned_tick_imbalance_5m=winner_median_5m,
                loser_median_side_aligned_tick_imbalance_5m=loser_median_5m,
                winner_minus_loser_tick_imbalance_5m=(
                    winner_median_5m - loser_median_5m
                    if winner_median_5m is not None
                    and loser_median_5m is not None
                    else None
                ),
                winner_median_side_aligned_tick_imbalance_15m=(
                    median(win_15m) if win_15m else None
                ),
                loser_median_side_aligned_tick_imbalance_15m=(
                    median(loss_15m) if loss_15m else None
                ),
                winner_pressure_agreement_rate=(
                    sum(winner_agreement) / len(winner_agreement)
                    if winner_agreement
                    else None
                ),
                loser_pressure_agreement_rate=(
                    sum(loser_agreement) / len(loser_agreement)
                    if loser_agreement
                    else None
                ),
                winner_median_spread_to_risk=(
                    median(row.spread_to_risk for row in wins)
                    if wins
                    else None
                ),
                loser_median_spread_to_risk=(
                    median(row.spread_to_risk for row in losses)
                    if losses
                    else None
                ),
                winner_median_path_efficiency_5m=(
                    median(row.path_efficiency_5m for row in wins)
                    if wins
                    else None
                ),
                loser_median_path_efficiency_5m=(
                    median(row.path_efficiency_5m for row in losses)
                    if losses
                    else None
                ),
                winner_precursor_rate=(
                    sum(row.precursor_first_seen_at is not None for row in wins)
                    / len(wins)
                    if wins
                    else None
                ),
                loser_precursor_rate=(
                    sum(row.precursor_first_seen_at is not None for row in losses)
                    / len(losses)
                    if losses
                    else None
                ),
                winner_precursor_patterns=dict(
                    Counter(
                        row.precursor_pattern.value
                        for row in wins
                        if row.precursor_pattern is not None
                    )
                ),
                loser_precursor_patterns=dict(
                    Counter(
                        row.precursor_pattern.value
                        for row in losses
                        if row.precursor_pattern is not None
                    )
                ),
            )
        )

    tick_all = [
        row for row in episodes if row.side_aligned_tick_imbalance_5m is not None
    ]
    return ProbeEarlyContextReport(
        generated_at=now,
        window_hours=window_hours,
        resolved_probes=len(probes),
        m1_eligible_probes=len(episodes),
        tick_pressure_eligible_probes=len(tick_all),
        tick_pressure_wins=sum(row.result_r > 0 for row in tick_all),
        tick_pressure_losses=sum(row.result_r < 0 for row in tick_all),
        summaries=sorted(
            summaries,
            key=lambda row: (
                -row.tick_pressure_eligible_probes,
                -row.m1_eligible_probes,
                row.strategy_id,
            ),
        ),
        recent_tick_pressure_probes=sorted(
            tick_all,
            key=lambda row: row.signal_at,
            reverse=True,
        )[:100],
        limitations=[
            (
                "This report uses resolved prospective unqualified probes only; "
                "it does not mix them with admitted PAPER/DEMO trades."
            ),
            (
                "M1 geometry is built only from microbars fully closed before probe "
                "signal_at and is never backfilled before the collector existed."
            ),
            (
                "A positive side-aligned tick imbalance is descriptive quote-direction "
                "pressure, not a standalone edge claim and not Level-2 OFI."
            ),
            (
                "Winner/loser medians remain descriptive until both classes have "
                "enough genuinely post-deployment tick-pressure observations."
            ),
        ],
    )


def _build_waiting_early_context_report(
    *,
    opportunities: list[MarketOpportunityEpisode],
    precursors: list[CausalPrecursorObservation],
    runtime_dir: Path,
    now: datetime,
    window_hours: int,
) -> WaitingEarlyContextReport:
    symbols = sorted({row.symbol.upper() for row in opportunities})
    microbars_by_symbol = {
        symbol: load_xau_microbars(runtime_dir / microbar_ledger_file(symbol))
        for symbol in symbols
    }
    coverage_started_at = {
        symbol: rows[0].minute_at
        for symbol, rows in microbars_by_symbol.items()
        if rows
    }
    precursors_by_symbol: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in precursors:
        precursors_by_symbol[row.symbol.upper()].append(row)
    for rows in precursors_by_symbol.values():
        rows.sort(key=lambda item: item.first_seen_at)

    waiting = [
        row
        for row in opportunities
        if row.first_signal_at is not None
        and row.first_signal_strategy_id is not None
        and row.first_signal_mechanism is not None
        and row.signal_lead_lag_minutes is not None
        and row.move_consumed_fraction is not None
        and row.move_consumed_at_signal_atr is not None
        and row.move_remaining_after_signal_atr is not None
    ]
    episodes: list[WaitingEarlyContextEpisode] = []
    grouped_waiting: dict[str, list[MarketOpportunityEpisode]] = defaultdict(list)
    for row in waiting:
        grouped_waiting[row.first_signal_strategy_id].append(row)
        microbars = _microbars_closed_before(
            microbars_by_symbol.get(row.symbol.upper(), []),
            row.first_signal_at,
            minutes=15,
        )
        geometry_5m = _geometry_window(microbars, 5) if microbars else None
        geometry_15m = _geometry_window(microbars, 15) if microbars else None
        if geometry_5m is None:
            continue
        precursor = _latest_matching_precursor_before_signal(
            precursors_by_symbol.get(row.symbol.upper(), []),
            side=row.side,
            signal_at=row.first_signal_at,
        )
        episodes.append(
            WaitingEarlyContextEpisode(
                episode_id=row.episode_id,
                strategy_id=row.first_signal_strategy_id,
                symbol=row.symbol,
                mechanism=row.first_signal_mechanism,
                side=row.side,
                first_signal_at=row.first_signal_at,
                signal_lead_lag_minutes=row.signal_lead_lag_minutes,
                move_consumed_fraction=row.move_consumed_fraction,
                move_consumed_at_signal_atr=row.move_consumed_at_signal_atr,
                move_remaining_after_signal_atr=row.move_remaining_after_signal_atr,
                directional_tick_samples_5m=geometry_5m.directional_tick_samples,
                side_aligned_tick_imbalance_5m=_side_aligned_imbalance(
                    row.side,
                    geometry_5m.mid_tick_imbalance,
                ),
                directional_tick_samples_15m=(
                    geometry_15m.directional_tick_samples
                    if geometry_15m is not None
                    else 0
                ),
                side_aligned_tick_imbalance_15m=(
                    _side_aligned_imbalance(
                        row.side,
                        geometry_15m.mid_tick_imbalance,
                    )
                    if geometry_15m is not None
                    else None
                ),
                precursor_first_seen_at=(
                    precursor.first_seen_at if precursor is not None else None
                ),
                precursor_pattern=(
                    precursor.pattern if precursor is not None else None
                ),
                precursor_lead_minutes_to_signal=(
                    (row.first_signal_at - precursor.first_seen_at).total_seconds()
                    / 60.0
                    if precursor is not None
                    else None
                ),
            )
        )

    grouped_eligible: dict[str, list[WaitingEarlyContextEpisode]] = defaultdict(list)
    for row in episodes:
        grouped_eligible[row.strategy_id].append(row)

    summaries: list[WaitingEarlyContextSummary] = []
    for strategy_id, waiting_rows in grouped_waiting.items():
        eligible = grouped_eligible.get(strategy_id, [])
        early = [
            row
            for row in eligible
            if row.move_consumed_fraction < WAITING_TARGET_MIN_CONSUMED_FRACTION
        ]
        target = [
            row
            for row in eligible
            if WAITING_TARGET_MIN_CONSUMED_FRACTION
            <= row.move_consumed_fraction
            <= WAITING_TARGET_MAX_CONSUMED_FRACTION
        ]
        late = [
            row
            for row in eligible
            if row.move_consumed_fraction > WAITING_TARGET_MAX_CONSUMED_FRACTION
        ]
        first = waiting_rows[0]
        target_imbalance_5m = _nonnull(
            row.side_aligned_tick_imbalance_5m for row in target
        )
        early_imbalance_5m = _nonnull(
            row.side_aligned_tick_imbalance_5m for row in early
        )
        target_imbalance_15m = _nonnull(
            row.side_aligned_tick_imbalance_15m for row in target
        )
        early_imbalance_15m = _nonnull(
            row.side_aligned_tick_imbalance_15m for row in early
        )
        tick_pressure_eligible = [
            row
            for row in eligible
            if row.side_aligned_tick_imbalance_5m is not None
        ]
        target_tick_pressure = [
            row
            for row in target
            if row.side_aligned_tick_imbalance_5m is not None
        ]
        target_precursors = sum(
            row.precursor_first_seen_at is not None for row in target
        )
        target_median_5m = (
            median(target_imbalance_5m) if target_imbalance_5m else None
        )
        early_median_5m = (
            median(early_imbalance_5m) if early_imbalance_5m else None
        )
        summaries.append(
            WaitingEarlyContextSummary(
                strategy_id=strategy_id,
                symbol=first.symbol,
                mechanism=first.first_signal_mechanism,
                waiting_episodes=len(waiting_rows),
                m1_eligible_episodes=len(eligible),
                tick_pressure_eligible_episodes=len(tick_pressure_eligible),
                early_reaction_m1_episodes=len(early),
                target_band_m1_episodes=len(target),
                target_band_tick_pressure_episodes=len(target_tick_pressure),
                late_reaction_m1_episodes=len(late),
                target_band_with_precursor=target_precursors,
                target_band_precursor_rate=(
                    target_precursors / len(target) if target else None
                ),
                median_target_directional_tick_samples_5m=(
                    median(
                        row.directional_tick_samples_5m
                        for row in target
                    )
                    if target
                    else None
                ),
                median_target_side_aligned_tick_imbalance_5m=target_median_5m,
                median_early_side_aligned_tick_imbalance_5m=early_median_5m,
                target_minus_early_tick_imbalance_5m=(
                    target_median_5m - early_median_5m
                    if target_median_5m is not None
                    and early_median_5m is not None
                    else None
                ),
                median_target_side_aligned_tick_imbalance_15m=(
                    median(target_imbalance_15m)
                    if target_imbalance_15m
                    else None
                ),
                median_early_side_aligned_tick_imbalance_15m=(
                    median(early_imbalance_15m)
                    if early_imbalance_15m
                    else None
                ),
            )
        )

    target_waiting = [
        row
        for row in waiting
        if WAITING_TARGET_MIN_CONSUMED_FRACTION
        <= row.move_consumed_fraction
        <= WAITING_TARGET_MAX_CONSUMED_FRACTION
    ]
    target_eligible = [
        row
        for row in episodes
        if WAITING_TARGET_MIN_CONSUMED_FRACTION
        <= row.move_consumed_fraction
        <= WAITING_TARGET_MAX_CONSUMED_FRACTION
    ]
    return WaitingEarlyContextReport(
        generated_at=now,
        window_hours=window_hours,
        target_band_min_fraction=WAITING_TARGET_MIN_CONSUMED_FRACTION,
        target_band_max_fraction=WAITING_TARGET_MAX_CONSUMED_FRACTION,
        m1_coverage_started_at=coverage_started_at,
        waiting_episodes=len(waiting),
        m1_eligible_episodes=len(episodes),
        tick_pressure_eligible_episodes=sum(
            row.side_aligned_tick_imbalance_5m is not None for row in episodes
        ),
        target_band_episodes=len(target_waiting),
        target_band_m1_eligible_episodes=len(target_eligible),
        target_band_tick_pressure_eligible_episodes=sum(
            row.side_aligned_tick_imbalance_5m is not None
            for row in target_eligible
        ),
        target_band_with_precursor=sum(
            row.precursor_first_seen_at is not None for row in target_eligible
        ),
        summaries=sorted(
            summaries,
            key=lambda row: (
                -row.target_band_m1_episodes,
                -row.m1_eligible_episodes,
                row.strategy_id,
            ),
        ),
        recent_m1_episodes=sorted(
            episodes,
            key=lambda row: row.first_signal_at,
            reverse=True,
        )[:100],
        limitations=[
            (
                "M1 pressure is computed only from microbars fully closed before the "
                "first SHADOW reaction; no pre-collector backfill is performed."
            ),
            (
                "The 25-40% consumed band is a descriptive research cohort requested "
                "for diagnosis, not a trading threshold."
            ),
            (
                "Positive side-aligned tick imbalance means quote-direction pressure "
                "matched the later market-opportunity side; this is not Level-2 OFI."
            ),
            (
                "A precursor counts only when the same-symbol/same-side observation "
                "was first seen within 15 minutes before the first SHADOW reaction."
            ),
        ],
    )


def _microbars_closed_before(
    rows: list[XauMicrobarM1],
    signal_at: datetime,
    *,
    minutes: int,
) -> list[XauMicrobarM1]:
    start_at = signal_at - timedelta(minutes=minutes)
    return [
        row
        for row in rows
        if start_at <= row.minute_at + timedelta(minutes=1) <= signal_at
    ]


def _latest_matching_precursor_before_signal(
    rows: list[CausalPrecursorObservation],
    *,
    side: Side,
    signal_at: datetime,
) -> CausalPrecursorObservation | None:
    start_at = signal_at - timedelta(
        minutes=5 * SIGNAL_CAPTURE_WINDOW_BARS
    )
    matches = [
        row
        for row in rows
        if row.side == side and start_at <= row.first_seen_at <= signal_at
    ]
    return max(matches, key=lambda row: row.first_seen_at) if matches else None


def _pressure_agreement(
    five_minute: float | None,
    fifteen_minute: float | None,
) -> bool | None:
    if five_minute is None or fifteen_minute is None:
        return None
    if five_minute == 0 and fifteen_minute == 0:
        return True
    return (
        (five_minute > 0 and fifteen_minute > 0)
        or (five_minute < 0 and fifteen_minute < 0)
    )


def _side_aligned_imbalance(
    side: Side,
    imbalance: float | None,
) -> float | None:
    if imbalance is None:
        return None
    return imbalance if side == Side.BUY else -imbalance


def _nonnull(values: Iterable[float | None]) -> list[float]:
    return [value for value in values if value is not None]


def _atr_series(bars: list[MarketBar], period: int = 14) -> list[float]:
    values: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        values.append(true_range)
        previous_close = bar.close

    output: list[float] = []
    for index in range(len(values)):
        start = max(0, index - period + 1)
        window = values[start : index + 1]
        output.append(sum(window) / len(window))
    return output


def _asset_summaries(
    *,
    symbols: list[str],
    trades: list[TradeIntelligence],
    opportunities: list[MarketOpportunityEpisode],
) -> list[AssetIntelligence]:
    output: list[AssetIntelligence] = []
    for symbol in symbols:
        paper = [
            row
            for row in trades
            if row.symbol.upper() == symbol
            and row.source == "paper"
            and row.status != PaperTradeStatus.OPEN.value
        ]
        blocked = [
            row
            for row in trades
            if row.symbol.upper() == symbol
            and row.source == "blocked_probe"
            and row.status != PaperTradeStatus.OPEN.value
        ]
        market = [row for row in opportunities if row.symbol.upper() == symbol]
        executable = sum(
            row.capture_state == OpportunityCaptureState.EXECUTABLE for row in market
        )
        captured_blocked = sum(
            row.capture_state == OpportunityCaptureState.BLOCKED for row in market
        )
        missed = sum(
            row.capture_state == OpportunityCaptureState.MISSED for row in market
        )
        captured = executable + captured_blocked
        output.append(
            AssetIntelligence(
                symbol=symbol,
                paper_closed_trades=len(paper),
                paper_total_r=sum(row.result_r or 0.0 for row in paper),
                blocked_closed_probes=len(blocked),
                blocked_total_r=sum(row.result_r or 0.0 for row in blocked),
                market_opportunities=len(market),
                captured_executable=executable,
                captured_blocked=captured_blocked,
                missed_opportunities=missed,
                capture_rate=(captured / len(market)) if market else 0.0,
                average_r_lost_while_waiting=(
                    fmean(row.r_lost_while_waiting for row in paper)
                    if paper
                    else 0.0
                ),
                average_mfe_r=(
                    fmean(row.mfe_r for row in paper) if paper else 0.0
                ),
                average_mae_r=(
                    fmean(row.mae_r for row in paper) if paper else 0.0
                ),
            )
        )
    return output


def _causal_pattern_summaries(
    opportunities: list[MarketOpportunityEpisode],
) -> list[OpportunityCausalPatternSummary]:
    grouped: dict[OpportunityCausalPattern, list[MarketOpportunityEpisode]] = (
        defaultdict(list)
    )
    for row in opportunities:
        grouped[row.causal_context.pattern].append(row)

    summaries: list[OpportunityCausalPatternSummary] = []
    for pattern, rows in grouped.items():
        aligned = sum(
            row.causal_context.aligned_with_move is True for row in rows
        )
        opposed = sum(
            row.causal_context.aligned_with_move is False for row in rows
        )
        no_direction = sum(
            row.causal_context.aligned_with_move is None for row in rows
        )
        summaries.append(
            OpportunityCausalPatternSummary(
                pattern=pattern,
                episodes=len(rows),
                missed=sum(
                    row.capture_state == OpportunityCaptureState.MISSED
                    for row in rows
                ),
                aligned=aligned,
                opposed=opposed,
                no_direction=no_direction,
                average_move_atr=fmean(row.move_atr for row in rows),
            )
        )

    return sorted(
        summaries,
        key=lambda row: (-row.episodes, row.pattern.value),
    )


def _unseen_pattern_summaries(
    opportunities: list[MarketOpportunityEpisode],
) -> list[UnseenOpportunityPatternSummary]:
    grouped: dict[OpportunityCausalPattern, list[MarketOpportunityEpisode]] = (
        defaultdict(list)
    )
    for row in opportunities:
        if row.detection_stage == OpportunityDetectionStage.UNSEEN:
            grouped[row.causal_context.pattern].append(row)

    summaries: list[UnseenOpportunityPatternSummary] = []
    for pattern, rows in grouped.items():
        symbols = Counter(row.symbol.upper() for row in rows)
        opposed = sum(
            row.causal_context.aligned_with_move is False for row in rows
        )
        neutral = sum(
            row.causal_context.aligned_with_move is None for row in rows
        )
        summaries.append(
            UnseenOpportunityPatternSummary(
                pattern=pattern,
                episodes=len(rows),
                buy_episodes=sum(row.side == Side.BUY for row in rows),
                sell_episodes=sum(row.side == Side.SELL for row in rows),
                symbols=dict(sorted(symbols.items())),
                average_move_atr=fmean(row.move_atr for row in rows),
                opposed_context_rate=opposed / len(rows),
                neutral_context_rate=neutral / len(rows),
                average_abs_return_6_atr=fmean(
                    abs(row.causal_context.return_6_atr) for row in rows
                ),
                average_compression_6_24=fmean(
                    row.causal_context.compression_6_24 for row in rows
                ),
            )
        )

    return sorted(
        summaries,
        key=lambda row: (-row.episodes, -row.average_move_atr, row.pattern.value),
    )


INTELLIGENCE_FILE = "trading_intelligence_latest.json"


def write_trading_intelligence(path: Path, overview: TradingIntelligenceOverview) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(overview.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def load_trading_intelligence(path: Path) -> TradingIntelligenceOverview | None:
    if not path.is_file():
        return None
    try:
        return TradingIntelligenceOverview.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
