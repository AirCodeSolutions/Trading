from collections.abc import Sequence
from typing import NamedTuple

from app.domain.market import MarketBar
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.trading import Side


class TriggerInspection(NamedTuple):
    side: Side
    raw_stop: float
    target_r: float
    max_holding_bars: int
    stop_atr: float
    move_atr: float | None
    retest_atr: float | None
    confirmation_atr: float | None
    close_location: float | None
    reason: str


def inspect_directional_pullback_trigger(
    bars: Sequence[MarketBar], atr: Sequence[float], regime: RegimeSnapshot
) -> TriggerInspection | None:
    if len(bars) < 3 or regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
        return None
    index = len(bars) - 1
    value = atr[index]
    if value <= 0:
        return None
    first_pullback, second_pullback, confirmation = bars[index - 2 : index + 1]
    side = Side.BUY if regime.direction > 0 else Side.SELL
    bar_range = confirmation.high - confirmation.low
    close_location = (confirmation.close - confirmation.low) / bar_range if bar_range > 0 else None
    if side == Side.BUY:
        valid = (
            first_pullback.close < first_pullback.open
            and second_pullback.close < second_pullback.open
            and confirmation.close > confirmation.open
            and confirmation.close > second_pullback.high
        )
        raw_stop = min(first_pullback.low, second_pullback.low) - 0.10 * value
    else:
        valid = (
            first_pullback.close > first_pullback.open
            and second_pullback.close > second_pullback.open
            and confirmation.close < confirmation.open
            and confirmation.close < second_pullback.low
        )
        raw_stop = max(first_pullback.high, second_pullback.high) + 0.10 * value
    if not valid or raw_stop <= 0:
        return None
    return TriggerInspection(
        side, raw_stop, 2.0, 12, 0.0, None, None, None, close_location,
        "directional M15 with two-bar M5 pullback and local-swing resumption",
    )


def inspect_break_retest_trigger(
    bars: Sequence[MarketBar], atr: Sequence[float], regime: RegimeSnapshot
) -> TriggerInspection | None:
    if regime.regime != MarketRegime.DIRECTIONAL or regime.direction == 0:
        return None
    index = len(bars) - 1
    bar = bars[index]
    value = atr[index]
    base = bars[index - 15 : index - 3]
    recent = bars[index - 3 : index]
    if value <= 0 or not base or not recent:
        return None
    prior_high = max(item.high for item in base)
    prior_low = min(item.low for item in base)
    bar_range = bar.high - bar.low
    if bar_range <= 0:
        return None
    close_location = (bar.close - bar.low) / bar_range
    if regime.direction > 0:
        breakout = max(item.close for item in recent) > prior_high + 0.05 * value
        retest = bar.low <= prior_high + 0.30 * value and bar.close > prior_high and bar.close > bar.open and close_location >= 0.60
        if not (breakout and retest):
            return None
        return TriggerInspection(
            Side.BUY, bar.low - 0.10 * value, 1.8, 18, 0.65 * value,
            (max(item.close for item in recent) - prior_high) / value,
            (prior_high - bar.low) / value,
            (bar.close - prior_high) / value,
            close_location,
            "directional M15 with M5 break, retest and re-acceleration",
        )
    breakout = min(item.close for item in recent) < prior_low - 0.05 * value
    retest = bar.high >= prior_low - 0.30 * value and bar.close < prior_low and bar.close < bar.open and close_location <= 0.40
    if not (breakout and retest):
        return None
    return TriggerInspection(
        Side.SELL, bar.high + 0.10 * value, 1.8, 18, 0.65 * value,
        (prior_low - min(item.close for item in recent)) / value,
        (bar.high - prior_low) / value,
        (prior_low - bar.close) / value,
        close_location,
        "directional M15 with M5 break, retest and re-acceleration",
    )
