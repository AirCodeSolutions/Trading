from datetime import datetime, timedelta

from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateFreshness
from app.services.market_state import build_market_state


def bars(symbol: str, timeframe: Timeframe, count: int, start: datetime, step: float = 0.1):
    minutes = 5 if timeframe == Timeframe.M5 else 15
    result = []
    price = 100.0
    for index in range(count):
        close = price + step
        result.append(
            MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start + timedelta(minutes=index * minutes),
                open=price,
                high=max(price, close) + 0.02,
                low=min(price, close) - 0.02,
                close=close,
            )
        )
        price = close
    return result


def test_market_state_uses_only_closed_bars_and_exposes_continuous_features():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m5 = bars("XAUUSD", Timeframe.M5, 60, start)
    m15 = bars("XAUUSD", Timeframe.M15, 55, start)
    evaluated_at = start + timedelta(minutes=60 * 5 + 5)
    state = build_market_state("XAUUSD", evaluated_at, m5, m15)

    assert state.latest_closed_m5_at == m5[-1].timestamp
    assert state.m5_freshness == MarketStateFreshness.FRESH
    assert state.momentum_atr is not None
    assert state.persistence is not None
    assert state.m1.available is False


def test_future_bars_do_not_change_state_before_their_close():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m5 = bars("BTCUSD", Timeframe.M5, 60, start)
    m15 = bars("BTCUSD", Timeframe.M15, 55, start)
    evaluated_at = start + timedelta(minutes=60 * 5)
    baseline = build_market_state("BTCUSD", evaluated_at, m5, m15)
    future = MarketBar(
        symbol="BTCUSD", timeframe=Timeframe.M5,
        timestamp=evaluated_at, open=101, high=1000, low=1, close=500,
    )
    changed = build_market_state("BTCUSD", evaluated_at, [*m5, future], m15)
    assert changed.latest_closed_m5_at == baseline.latest_closed_m5_at
    assert changed.momentum_atr == baseline.momentum_atr


def test_missing_history_is_explicit_and_stale_is_not_fresh():
    evaluated_at = datetime(2026, 9, 30, 12, tzinfo=datetime.now().astimezone().tzinfo)
    state = build_market_state("EURUSD", evaluated_at, [], [])
    assert state.m5_freshness == MarketStateFreshness.UNAVAILABLE
    assert state.m15_freshness == MarketStateFreshness.UNAVAILABLE
    assert state.atr_m5 is None

    old = bars("EURUSD", Timeframe.M5, 10, evaluated_at - timedelta(hours=3))
    stale = build_market_state("EURUSD", evaluated_at, old, [])
    assert stale.m5_freshness == MarketStateFreshness.STALE


def test_all_configured_symbols_can_be_serialized_without_execution_fields():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    for symbol in ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"):
        state = build_market_state(symbol, start, [], [])
        payload = state.model_dump(mode="json")
        assert payload["symbol"] == symbol
        assert "order" not in payload
        assert "sizing" not in payload
