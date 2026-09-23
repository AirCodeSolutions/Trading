from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    AssetIntelligence,
    MarketOpportunityEpisode,
    OpportunityCaptureState,
    OpportunityCausalContext,
    OpportunityCausalPattern,
    OpportunityCausalPatternSummary,
    TradeIntelligence,
    TradingIntelligenceOverview,
)
from app.services.blocked_probe import load_blocked_probe_state, load_closed_probes
from app.services.causal_precursor import (
    load_causal_precursor_collection_state,
    load_causal_precursors,
)
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.shadow_paper import load_closed_trades, load_shadow_paper_state

DEFAULT_WINDOW_HOURS = 48
MARKET_MOVE_THRESHOLD_ATR = 1.5
MARKET_MOVE_HORIZON_BARS = 12
SIGNAL_CAPTURE_WINDOW_BARS = 3


def build_trading_intelligence(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    symbols: tuple[str, ...] | None = None,
    market_move_threshold_atr: float = MARKET_MOVE_THRESHOLD_ATR,
    market_move_horizon_bars: int = MARKET_MOVE_HORIZON_BARS,
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

    assets = _asset_summaries(
        symbols=sorted(discovered_symbols),
        trades=trade_rows,
        opportunities=opportunities,
    )
    causal_patterns = _causal_pattern_summaries(opportunities)
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
        average_precursor_lead_minutes=(
            fmean(precursor_leads) if precursor_leads else 0.0
        ),
        trades=trade_rows[:100],
        opportunities=opportunities[:200],
        assets=assets,
        causal_patterns=causal_patterns,
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
                matching_strategies=strategies,
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
                causal_context=causal_context,
            )
        )
        index += horizon_bars
    return episodes


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
