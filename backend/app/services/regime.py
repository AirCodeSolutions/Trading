from collections.abc import Sequence
from statistics import median

from app.domain.market import MarketBar
from app.domain.regime import MarketRegime, RegimeSnapshot


def _true_ranges(bars: Sequence[MarketBar]) -> list[float]:
    ranges: list[float] = []
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
        ranges.append(value)
        previous_close = bar.close
    return ranges


def _rolling_atr(true_ranges: Sequence[float], period: int = 14) -> list[float]:
    values: list[float] = []
    for index in range(len(true_ranges)):
        start = max(0, index - period + 1)
        window = true_ranges[start : index + 1]
        values.append(sum(window) / len(window))
    return values


def _efficiency(bars: Sequence[MarketBar], lookback: int = 12) -> float:
    window = bars[-(lookback + 1) :]
    if len(window) < 2:
        return 0.0
    net = abs(window[-1].close - window[0].close)
    path = sum(abs(window[index].close - window[index - 1].close) for index in range(1, len(window)))
    return min(1.0, net / path) if path > 0 else 0.0


def classify_regime(bars: Sequence[MarketBar]) -> RegimeSnapshot:
    if not bars:
        raise ValueError("at least one bar is required")

    latest = bars[-1]
    if len(bars) < 50:
        return RegimeSnapshot(
            symbol=latest.symbol,
            at=latest.timestamp,
            regime=MarketRegime.WARMUP,
            direction=0,
            confidence=0,
            atr=0,
            atr_ratio=0,
            efficiency=0,
            shock_ratio=0,
            reason="fewer than 50 M15 bars",
        )

    true_ranges = _true_ranges(bars)
    atr_values = _rolling_atr(true_ranges)
    atr = atr_values[-1]
    baseline = median(atr_values[-50:-1])
    atr_ratio = atr / baseline if baseline > 0 else 0.0
    previous_atr = atr_values[-2]
    shock_ratio = true_ranges[-1] / previous_atr if previous_atr > 0 else 0.0
    efficiency = _efficiency(bars)

    direction = 0
    lookback_close = bars[-13].close
    if latest.close > lookback_close:
        direction = 1
    elif latest.close < lookback_close:
        direction = -1

    body = abs(latest.close - latest.open)
    bar_range = latest.high - latest.low
    body_fraction = body / bar_range if bar_range > 0 else 0.0
    close_location = (latest.close - latest.low) / bar_range if bar_range > 0 else 0.5
    closes_near_extreme = close_location >= 0.78 or close_location <= 0.22

    if shock_ratio >= 1.5 and body_fraction >= 0.65 and closes_near_extreme:
        shock_direction = 1 if latest.close > latest.open else -1
        return RegimeSnapshot(
            symbol=latest.symbol,
            at=latest.timestamp,
            regime=MarketRegime.POST_SHOCK,
            direction=shock_direction,
            confidence=min(1.0, 0.55 + 0.2 * (shock_ratio - 1.5) + 0.25 * body_fraction),
            atr=atr,
            atr_ratio=atr_ratio,
            efficiency=efficiency,
            shock_ratio=shock_ratio,
            reason="large directional information bar relative to prior ATR",
        )

    if atr_ratio < 0.70:
        return RegimeSnapshot(
            symbol=latest.symbol,
            at=latest.timestamp,
            regime=MarketRegime.DEAD,
            direction=0,
            confidence=min(1.0, (0.70 - atr_ratio) / 0.35 + 0.5),
            atr=atr,
            atr_ratio=atr_ratio,
            efficiency=efficiency,
            shock_ratio=shock_ratio,
            reason="rolling volatility is materially below its local baseline",
        )

    if efficiency >= 0.55 and atr_ratio >= 0.90 and direction != 0:
        return RegimeSnapshot(
            symbol=latest.symbol,
            at=latest.timestamp,
            regime=MarketRegime.DIRECTIONAL,
            direction=direction,
            confidence=min(1.0, 0.45 + 0.55 * efficiency),
            atr=atr,
            atr_ratio=atr_ratio,
            efficiency=efficiency,
            shock_ratio=shock_ratio,
            reason="directional efficiency and volatility jointly support trend conditions",
        )

    return RegimeSnapshot(
        symbol=latest.symbol,
        at=latest.timestamp,
        regime=MarketRegime.BALANCED,
        direction=0,
        confidence=min(1.0, 0.5 + 0.4 * (1.0 - efficiency)),
        atr=atr,
        atr_ratio=atr_ratio,
        efficiency=efficiency,
        shock_ratio=shock_ratio,
        reason="no directional, shock or dead-market condition is dominant",
    )
