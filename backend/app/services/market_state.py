from collections.abc import Sequence
from datetime import datetime, timedelta
from itertools import pairwise

from app.domain.live_market import LiveMarketQuote
from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateFreshness, MarketStateM1Context, MarketStateV2
from app.domain.session_landmark import SessionLandmarkContext
from app.domain.trading import Side
from app.services.macro_gate import macro_gate_status
from app.services.opportunity_strategies import _atr_series
from app.services.regime import classify_regime
from app.services.session_landmarks import build_session_landmark_context


def _closed(bars: Sequence[MarketBar], timeframe: Timeframe, at: datetime) -> list[MarketBar]:
    minutes = 5 if timeframe == Timeframe.M5 else 15
    return sorted(
        (bar for bar in bars if bar.timestamp + timedelta(minutes=minutes) <= at),
        key=lambda bar: bar.timestamp,
    )


def _freshness(latest: datetime | None, at: datetime, timeframe_minutes: int) -> MarketStateFreshness:
    if latest is None:
        return MarketStateFreshness.UNAVAILABLE
    return (
        MarketStateFreshness.FRESH
        if (at - (latest + timedelta(minutes=timeframe_minutes))).total_seconds() <= timeframe_minutes * 3 * 60
        else MarketStateFreshness.STALE
    )


def _m5_features(bars: Sequence[MarketBar], atr: float | None) -> dict[str, float | int | None]:
    if len(bars) < 8 or atr is None or atr <= 0:
        return {}
    closes = [bar.close for bar in bars]
    recent = closes[-4:]
    previous = closes[-8:-4]
    path = sum(abs(b - a) for a, b in pairwise(recent))
    efficiency = abs(recent[-1] - recent[0]) / path if path else 0.0
    momentum = (recent[-1] - recent[0]) / atr
    previous_momentum = (previous[-1] - previous[0]) / atr
    persistence = sum(1 if b > a else -1 if b < a else 0 for a, b in pairwise(recent)) / 3
    direction = 1 if momentum > 0 else -1 if momentum < 0 else 0
    window = closes[-8:]
    extension = ((closes[-1] - min(window)) if direction > 0 else (max(window) - closes[-1])) / atr if direction else None
    structure_distance = min(abs(closes[-1] - min(window)), abs(max(window) - closes[-1])) / atr
    ranges = [bar.high - bar.low for bar in bars[-8:]]
    baseline = sum(ranges[:-1]) / len(ranges[:-1]) if ranges[:-1] else 0
    expansion = ranges[-1] / baseline if baseline > 0 else None
    return {
        "direction": direction,
        "persistence": persistence,
        "persistence_magnitude": abs(persistence),
        "momentum": momentum,
        "acceleration": momentum - previous_momentum,
        "efficiency": efficiency,
        "extension": extension,
        "structure_distance": structure_distance,
        "expansion": expansion,
        "exhaustion": abs(momentum) * (1 - efficiency),
    }


def build_market_state(
    symbol: str,
    evaluated_at: datetime,
    bars_m5: Sequence[MarketBar],
    bars_m15: Sequence[MarketBar],
    *,
    quote: LiveMarketQuote | None = None,
    macro_path=None,
) -> MarketStateV2:
    m5 = _closed(bars_m5, Timeframe.M5, evaluated_at)
    m15 = _closed(bars_m15, Timeframe.M15, evaluated_at)
    atr_m5 = _atr_series(m5)[-1] if m5 else None
    regime = classify_regime(m15) if m15 else None
    price = quote.mid if quote else (m5[-1].close if m5 else None)
    side = Side.BUY if not regime or regime.direction >= 0 else Side.SELL
    landmarks: SessionLandmarkContext | None = (
        build_session_landmark_context(m5, evaluated_at, price, side, atr_m5=atr_m5, atr_m15=regime.atr if regime else None)
        if price is not None else None
    )
    features = _m5_features(m5, atr_m5)
    return MarketStateV2(
        symbol=symbol, evaluated_at=evaluated_at,
        latest_closed_m5_at=m5[-1].timestamp if m5 else None,
        latest_closed_m15_at=m15[-1].timestamp if m15 else None,
        m5_freshness=_freshness(m5[-1].timestamp if m5 else None, evaluated_at, 5),
        m15_freshness=_freshness(m15[-1].timestamp if m15 else None, evaluated_at, 15),
        regime=regime.regime.value if regime else None,
        regime_direction=regime.direction if regime else None,
        regime_confidence=regime.confidence if regime else None,
        atr_m15=regime.atr if regime else None,
        atr_ratio_m15=regime.atr_ratio if regime else None,
        efficiency_m15=regime.efficiency if regime else None,
        atr_m5=atr_m5,
        m5_direction=features.get("direction"), persistence=features.get("persistence"),
        persistence_magnitude=features.get("persistence_magnitude"), momentum_atr=features.get("momentum"),
        acceleration_atr=features.get("acceleration"), efficiency_m5=features.get("efficiency"),
        extension_atr=features.get("extension"), distance_to_recent_structure_atr=features.get("structure_distance"),
        range_expansion_ratio=features.get("expansion"), exhaustion_proxy=features.get("exhaustion"),
        session_context=landmarks,
        macro=macro_gate_status(macro_path, evaluated_at) if macro_path is not None else None,
        spread=quote.spread if quote else None,
        spread_atr_m5=quote.spread / atr_m5 if quote and atr_m5 and atr_m5 > 0 else None,
        spread_atr_m15=quote.spread / regime.atr if quote and regime and regime.atr and regime.atr > 0 else None,
        m1=MarketStateM1Context(),
    )
