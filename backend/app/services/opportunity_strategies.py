from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.replay import RegimeReplay
from app.services.session_continuity import reopen_warmup_remaining
from app.services.trading_intelligence import _classify_causal_context

ATHENS = ZoneInfo("Europe/Athens")
ASIA_RANGE_START_HOUR = 2
ASIA_RANGE_END_HOUR = 10
LONDON_OBSERVATION_END_HOUR = 13
ASIA_RANGE_MIN_M5_BARS = 60

STRUCTURAL_DISPLACEMENT_SEQUENCE_PATTERNS = {
    "BTCUSD": (
        OpportunityCausalPattern.STRUCTURAL_EXTREME,
        OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
    ),
    "XAUUSD": (
        OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
        OpportunityCausalPattern.STRUCTURAL_EXTREME,
        OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
    ),
}
STRUCTURAL_PERSISTENCE_SEQUENCE_PATTERN = (
    OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
    OpportunityCausalPattern.STRUCTURAL_EXTREME,
    OpportunityCausalPattern.STRUCTURAL_EXTREME,
)


def _true_ranges(bars: Sequence[MarketBar]) -> list[float]:
    values: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            value = bar.high - bar.low
        else:
            value = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        values.append(value)
        previous_close = bar.close
    return values


def _atr_series(bars: Sequence[MarketBar], period: int = 14) -> list[float]:
    true_ranges = _true_ranges(bars)
    output: list[float] = []
    for index in range(len(true_ranges)):
        start = max(0, index - period + 1)
        window = true_ranges[start : index + 1]
        output.append(sum(window) / len(window))
    return output


def _regime_timeline(
    bars_m15: Sequence[MarketBar],
) -> tuple[list[datetime], list[RegimeSnapshot]]:
    snapshots = RegimeReplay().replay(bars_m15)
    close_times = [bar.timestamp + timedelta(minutes=15) for bar in bars_m15]
    return close_times, snapshots


def _regime_at(
    signal_close: datetime,
    close_times: Sequence[datetime],
    snapshots: Sequence[RegimeSnapshot],
) -> RegimeSnapshot | None:
    index = bisect_right(close_times, signal_close) - 1
    return snapshots[index] if index >= 0 else None


def generate_candidates(
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    mechanism: OpportunityMechanism,
) -> list[OpportunityCandidate]:
    if len(bars_m5) < 30 or len(bars_m15) < 50:
        return []

    close_times, regimes = _regime_timeline(bars_m15)
    atr_m5 = _atr_series(bars_m5)
    candidates: list[OpportunityCandidate] = []
    last_shock_at: datetime | None = None

    for index in range(25, len(bars_m5) - 1):
        if reopen_warmup_remaining(bars_m5, index) > 0:
            continue

        bar = bars_m5[index]
        signal_close = bar.timestamp + timedelta(minutes=5)

        if mechanism == OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL:
            candidate = _asia_range_sweep_candidate(
                bars_m5,
                atr_m5,
                index,
            )
            if candidate is not None:
                candidates.append(candidate)
            continue

        if mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE:
            candidate = _structural_displacement_sequence_candidate(
                bars_m5,
                atr_m5,
                index,
            )
            if candidate is not None:
                candidates.append(candidate)
            continue

        if mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE:
            candidate = _structural_persistence_sequence_candidate(
                bars_m5,
                atr_m5,
                index,
            )
            if candidate is not None:
                candidates.append(candidate)
            continue

        regime_index = bisect_right(close_times, signal_close) - 1
        regime = regimes[regime_index] if regime_index >= 0 else None
        if regime is None or regime.regime == MarketRegime.WARMUP:
            continue

        candidate = None
        if mechanism == OpportunityMechanism.POST_SHOCK_CONTINUATION:
            if regime.regime != MarketRegime.POST_SHOCK or regime.at == last_shock_at:
                continue
            candidate = _post_shock_candidate(
                bars_m5,
                index,
                regime,
            )
            if candidate is not None:
                last_shock_at = regime.at

        elif mechanism == OpportunityMechanism.BREAK_RETEST_REACCEL:
            if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
                continue
            candidate = _break_retest_candidate(
                bars_m5,
                atr_m5,
                index,
                regime,
            )

        elif mechanism == OpportunityMechanism.FAILED_AUCTION_REVERSAL:
            if regime.regime != MarketRegime.BALANCED:
                continue
            candidate = _failed_auction_candidate(
                bars_m5,
                atr_m5,
                index,
            )

        elif mechanism == OpportunityMechanism.DIRECTIONAL_TRANSITION:
            if regime_index < 1 or signal_close != close_times[regime_index]:
                continue
            previous_regime = regimes[regime_index - 1]
            if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
                continue
            if (
                previous_regime.regime == MarketRegime.DIRECTIONAL
                and previous_regime.direction == regime.direction
            ):
                continue
            candidate = _directional_transition_candidate(
                bars_m5,
                index,
                regime,
            )

        elif mechanism == OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION:
            if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
                continue
            candidate = _directional_pullback_resumption_candidate(
                bars_m5,
                atr_m5,
                index,
                regime,
            )

        if candidate is not None:
            candidates.append(candidate)

    return candidates


def _asia_range_sweep_match(
    signal: MarketBar,
    atr_value: float,
    asia_high: float,
    asia_low: float,
) -> tuple[Side, float, float, float, float] | None:
    bar_range = signal.high - signal.low
    if atr_value <= 0 or bar_range <= 0:
        return None

    upper_wick = signal.high - max(signal.open, signal.close)
    lower_wick = min(signal.open, signal.close) - signal.low
    close_location = (signal.close - signal.low) / bar_range

    if (
        signal.high > asia_high + 0.10 * atr_value
        and signal.close < asia_high - 0.02 * atr_value
        and upper_wick / bar_range >= 0.35
        and close_location <= 0.50
    ):
        return (
            Side.SELL,
            signal.high + 0.15 * atr_value,
            (signal.high - asia_high) / atr_value,
            (asia_high - signal.close) / atr_value,
            close_location,
        )

    if (
        signal.low < asia_low - 0.10 * atr_value
        and signal.close > asia_low + 0.02 * atr_value
        and lower_wick / bar_range >= 0.35
        and close_location >= 0.50
    ):
        return (
            Side.BUY,
            signal.low - 0.15 * atr_value,
            (asia_low - signal.low) / atr_value,
            (signal.close - asia_low) / atr_value,
            close_location,
        )
    return None


def _asia_range_sweep_geometry(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> tuple[Side, float, float, float, float] | None:
    if index < 0 or index >= len(bars) or index >= len(atr):
        return None

    signal = bars[index]
    if signal.timestamp.utcoffset() is None:
        return None
    signal_local = signal.timestamp.astimezone(ATHENS)
    asia_start = signal_local.replace(hour=ASIA_RANGE_START_HOUR, minute=0, second=0, microsecond=0)
    asia_end = signal_local.replace(hour=ASIA_RANGE_END_HOUR, minute=0, second=0, microsecond=0)
    observation_end = signal_local.replace(
        hour=LONDON_OBSERVATION_END_HOUR, minute=0, second=0, microsecond=0
    )
    if not (asia_end <= signal_local < observation_end):
        return None

    same_day: list[tuple[int, MarketBar, datetime]] = []
    for prior_index in range(index - 1, -1, -1):
        prior = bars[prior_index]
        if prior.timestamp.utcoffset() is None:
            continue
        prior_local = prior.timestamp.astimezone(ATHENS)
        if prior_local.date() != signal_local.date():
            if prior_local.date() < signal_local.date():
                break
            continue
        same_day.append((prior_index, prior, prior_local))

    asia_bars = [
        prior for _, prior, prior_local in same_day if asia_start <= prior_local < asia_end
    ]
    if len(asia_bars) < ASIA_RANGE_MIN_M5_BARS:
        return None

    asia_high = max(bar.high for bar in asia_bars)
    asia_low = min(bar.low for bar in asia_bars)

    for prior_index, prior, prior_local in same_day:
        if not (asia_end <= prior_local < signal_local):
            continue
        if _asia_range_sweep_match(prior, atr[prior_index], asia_high, asia_low) is not None:
            return None

    return _asia_range_sweep_match(signal, atr[index], asia_high, asia_low)


def _asia_range_sweep_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> OpportunityCandidate | None:
    if index + 1 >= len(bars):
        return None
    geometry = _asia_range_sweep_geometry(bars, atr, index)
    if geometry is None:
        return None
    side, stop, _, _, _ = geometry
    signal = bars[index]
    entry = bars[index + 1]
    return OpportunityCandidate(
        symbol=signal.symbol,
        mechanism=OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        side=side,
        signal_at=signal.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.5,
        max_holding_bars=12,
        reason="completed Athens Asia range sweep with causal reclaim",
    )


def _asia_range_sweep_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
):
    if not bars:
        return None
    geometry = _asia_range_sweep_geometry(bars, atr, len(bars) - 1)
    if geometry is None:
        return None
    side, stop, sweep_strength, reclaim, close_location = geometry
    return (
        side,
        stop,
        1.5,
        12,
        0.0,
        sweep_strength,
        None,
        reclaim,
        close_location,
        "completed Athens Asia range sweep with causal reclaim",
    )


def _structural_displacement_sequence_side(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> Side | None:
    if index < 26 or index >= len(bars) or index >= len(atr):
        return None
    expected_patterns = STRUCTURAL_DISPLACEMENT_SEQUENCE_PATTERNS.get(
        bars[index].symbol.upper()
    )
    if expected_patterns is None:
        return None

    contexts = [
        _classify_causal_context(
            bars=bars,  # type: ignore[arg-type]
            atr=atr,  # type: ignore[arg-type]
            index=context_index,
            episode_side=Side.BUY,
        )
        for context_index in range(index - 2, index + 1)
    ]
    patterns = tuple(context.pattern for context in contexts)
    if patterns != expected_patterns:
        return None
    return contexts[-1].side


def _structural_displacement_sequence_reason(symbol: str) -> str:
    patterns = STRUCTURAL_DISPLACEMENT_SEQUENCE_PATTERNS.get(symbol.upper(), ())
    return "causal three-state sequence: " + " -> ".join(
        pattern.value for pattern in patterns
    )


def _structural_displacement_sequence_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> OpportunityCandidate | None:
    if index + 1 >= len(bars):
        return None
    side = _structural_displacement_sequence_side(bars, atr, index)
    if side is None:
        return None

    atr_value = atr[index]
    if atr_value <= 0:
        return None
    entry = bars[index + 1]
    stop_distance = 1.50 * atr_value
    stop = (
        entry.open - stop_distance
        if side == Side.BUY
        else entry.open + stop_distance
    )
    if stop <= 0:
        return None

    signal = bars[index]
    return OpportunityCandidate(
        symbol=signal.symbol,
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=side,
        signal_at=signal.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.0,
        max_holding_bars=12,
        reason=_structural_displacement_sequence_reason(signal.symbol),
    )


def _structural_displacement_sequence_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
):
    if len(bars) < 27:
        return None
    index = len(bars) - 1
    side = _structural_displacement_sequence_side(bars, atr, index)
    if side is None:
        return None

    atr_value = atr[index]
    if atr_value <= 0:
        return None
    bar = bars[index]
    raw_stop = bar.low if side == Side.BUY else bar.high
    return (
        side,
        raw_stop,
        1.0,
        12,
        1.50 * atr_value,
        None,
        None,
        None,
        None,
        _structural_displacement_sequence_reason(bar.symbol),
    )


def _structural_persistence_sequence_side(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> Side | None:
    if index < 26 or index >= len(bars) or index >= len(atr):
        return None
    if bars[index].symbol.upper() != "XAUUSD":
        return None

    contexts = [
        _classify_causal_context(
            bars=bars,  # type: ignore[arg-type]
            atr=atr,  # type: ignore[arg-type]
            index=context_index,
            episode_side=Side.BUY,
        )
        for context_index in range(index - 2, index + 1)
    ]
    patterns = tuple(context.pattern for context in contexts)
    if patterns != STRUCTURAL_PERSISTENCE_SEQUENCE_PATTERN:
        return None

    for context in reversed(contexts):
        if context.side is not None:
            return context.side
    return None


def _structural_persistence_sequence_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> OpportunityCandidate | None:
    if index + 1 >= len(bars):
        return None
    side = _structural_persistence_sequence_side(bars, atr, index)
    if side is None:
        return None

    atr_value = atr[index]
    if atr_value <= 0:
        return None
    entry = bars[index + 1]
    stop_distance = 1.50 * atr_value
    stop = (
        entry.open - stop_distance
        if side == Side.BUY
        else entry.open + stop_distance
    )
    if stop <= 0:
        return None

    signal = bars[index]
    return OpportunityCandidate(
        symbol=signal.symbol,
        mechanism=OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
        side=side,
        signal_at=signal.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.0,
        max_holding_bars=12,
        reason=(
            "causal three-state sequence: directional_displacement -> "
            "structural_extreme -> structural_extreme"
        ),
    )


def _structural_persistence_sequence_signal(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
):
    if len(bars) < 27:
        return None
    index = len(bars) - 1
    side = _structural_persistence_sequence_side(bars, atr, index)
    if side is None:
        return None

    atr_value = atr[index]
    if atr_value <= 0:
        return None
    bar = bars[index]
    raw_stop = bar.low if side == Side.BUY else bar.high
    return (
        side,
        raw_stop,
        1.0,
        12,
        1.50 * atr_value,
        None,
        None,
        None,
        None,
        (
            "causal three-state sequence: directional_displacement -> "
            "structural_extreme -> structural_extreme"
        ),
    )


def _directional_pullback_resumption_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
    regime: RegimeSnapshot,
) -> OpportunityCandidate | None:
    if index < 2 or index + 1 >= len(bars):
        return None
    if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
        return None

    value = atr[index]
    if value <= 0:
        return None

    first_pullback = bars[index - 2]
    second_pullback = bars[index - 1]
    confirmation = bars[index]
    entry = bars[index + 1]
    side = Side.BUY if regime.direction > 0 else Side.SELL

    if side == Side.BUY:
        if not (
            first_pullback.close < first_pullback.open
            and second_pullback.close < second_pullback.open
            and confirmation.close > confirmation.open
            and confirmation.close > second_pullback.high
        ):
            return None
        swing = min(first_pullback.low, second_pullback.low)
        stop = swing - 0.10 * value
    else:
        if not (
            first_pullback.close > first_pullback.open
            and second_pullback.close > second_pullback.open
            and confirmation.close < confirmation.open
            and confirmation.close < second_pullback.low
        ):
            return None
        swing = max(first_pullback.high, second_pullback.high)
        stop = swing + 0.10 * value

    if stop <= 0:
        return None

    return OpportunityCandidate(
        symbol=confirmation.symbol,
        mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        side=side,
        signal_at=confirmation.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=2.0,
        max_holding_bars=12,
        reason=(
            "directional M15 with two-bar M5 pullback and local-swing resumption"
        ),
    )


def _directional_transition_candidate(
    bars: Sequence[MarketBar],
    index: int,
    regime: RegimeSnapshot,
) -> OpportunityCandidate | None:
    if regime.atr <= 0 or index + 1 >= len(bars):
        return None

    bar = bars[index]
    entry = bars[index + 1]
    side = Side.BUY if regime.direction > 0 else Side.SELL
    if side == Side.BUY:
        stop = entry.open - 0.80 * regime.atr
        if stop <= 0:
            return None
    else:
        stop = entry.open + 0.80 * regime.atr

    return OpportunityCandidate(
        symbol=bar.symbol,
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        side=side,
        signal_at=bar.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.8,
        max_holding_bars=18,
        reason="first causal M15 transition into directional expansion",
    )


def _post_shock_candidate(
    bars: Sequence[MarketBar],
    index: int,
    regime: RegimeSnapshot,
) -> OpportunityCandidate | None:
    bar = bars[index]
    bar_range = bar.high - bar.low
    if bar_range <= 0 or regime.atr <= 0:
        return None

    close_location = (bar.close - bar.low) / bar_range
    aligned = (
        regime.direction > 0
        and bar.close > bar.open
        and close_location >= 0.60
    ) or (
        regime.direction < 0
        and bar.close < bar.open
        and close_location <= 0.40
    )
    if not aligned or bar_range > 0.90 * regime.atr:
        return None

    entry = bars[index + 1]
    side = Side.BUY if regime.direction > 0 else Side.SELL
    if side == Side.BUY:
        stop = min(bar.low, entry.open - 0.65 * regime.atr)
    else:
        stop = max(bar.high, entry.open + 0.65 * regime.atr)

    return OpportunityCandidate(
        symbol=bar.symbol,
        mechanism=OpportunityMechanism.POST_SHOCK_CONTINUATION,
        side=side,
        signal_at=bar.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.8,
        max_holding_bars=12,
        reason="M15 information shock followed by aligned M5 confirmation",
    )


def _break_retest_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
    regime: RegimeSnapshot,
) -> OpportunityCandidate | None:
    bar = bars[index]
    value = atr[index]
    if value <= 0:
        return None

    base = bars[index - 15 : index - 3]
    recent = bars[index - 3 : index]
    if not base or not recent:
        return None

    prior_high = max(item.high for item in base)
    prior_low = min(item.low for item in base)
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return None
    close_location = (bar.close - bar.low) / bar_range

    side: Side | None = None
    if regime.direction > 0:
        breakout = max(item.close for item in recent) > prior_high + 0.05 * value
        retest = (
            bar.low <= prior_high + 0.30 * value
            and bar.close > prior_high
            and bar.close > bar.open
            and close_location >= 0.60
        )
        if breakout and retest:
            side = Side.BUY
    else:
        breakout = min(item.close for item in recent) < prior_low - 0.05 * value
        retest = (
            bar.high >= prior_low - 0.30 * value
            and bar.close < prior_low
            and bar.close < bar.open
            and close_location <= 0.40
        )
        if breakout and retest:
            side = Side.SELL

    if side is None:
        return None

    entry = bars[index + 1]
    if side == Side.BUY:
        stop = min(bar.low - 0.10 * value, entry.open - 0.65 * value)
    else:
        stop = max(bar.high + 0.10 * value, entry.open + 0.65 * value)

    return OpportunityCandidate(
        symbol=bar.symbol,
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=side,
        signal_at=bar.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.8,
        max_holding_bars=18,
        reason="M15 directional regime with M5 break, retest and re-acceleration",
    )


def _failed_auction_candidate(
    bars: Sequence[MarketBar],
    atr: Sequence[float],
    index: int,
) -> OpportunityCandidate | None:
    bar = bars[index]
    value = atr[index]
    if value <= 0:
        return None

    history = bars[index - 24 : index]
    prior_high = max(item.high for item in history)
    prior_low = min(item.low for item in history)
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return None

    upper_wick = bar.high - max(bar.open, bar.close)
    lower_wick = min(bar.open, bar.close) - bar.low
    close_location = (bar.close - bar.low) / bar_range
    side: Side | None = None

    if (
        bar.high > prior_high + 0.10 * value
        and bar.close < prior_high - 0.02 * value
        and upper_wick / bar_range >= 0.35
        and close_location <= 0.50
    ):
        side = Side.SELL
    elif (
        bar.low < prior_low - 0.10 * value
        and bar.close > prior_low + 0.02 * value
        and lower_wick / bar_range >= 0.35
        and close_location >= 0.50
    ):
        side = Side.BUY

    if side is None:
        return None

    entry = bars[index + 1]
    if side == Side.BUY:
        stop = min(bar.low - 0.15 * value, entry.open - 0.60 * value)
    else:
        stop = max(bar.high + 0.15 * value, entry.open + 0.60 * value)

    return OpportunityCandidate(
        symbol=bar.symbol,
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        side=side,
        signal_at=bar.timestamp + timedelta(minutes=5),
        entry_at=entry.timestamp,
        signal_index=index,
        entry_index=index + 1,
        structural_stop=stop,
        target_r=1.5,
        max_holding_bars=12,
        reason="M15 balanced auction with M5 sweep and causal reclaim",
    )
