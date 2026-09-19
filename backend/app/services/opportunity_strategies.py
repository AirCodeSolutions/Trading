from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.domain.market import MarketBar
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side
from app.services.replay import RegimeReplay


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
        bar = bars_m5[index]
        signal_close = bar.timestamp + timedelta(minutes=5)
        regime = _regime_at(signal_close, close_times, regimes)
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

        if candidate is not None:
            candidates.append(candidate)

    return candidates


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
