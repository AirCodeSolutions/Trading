from datetime import datetime, timedelta

from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateFreshness
from app.services.market_state import build_market_state
from app.services.regime import classify_regime
from app.services.replay import RegimeReplay


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


def test_regime_replay_and_final_classifier_are_equivalent():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m15 = bars("XAUUSD", Timeframe.M15, 55, start)
    assert RegimeReplay(max_history=250).replay(m15)[-1] == classify_regime(m15)


def test_future_m15_is_excluded_from_regime():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m15 = bars("XAUUSD", Timeframe.M15, 55, start)
    evaluated_at = m15[-1].timestamp + timedelta(minutes=15)
    future = MarketBar(symbol="XAUUSD", timeframe=Timeframe.M15, timestamp=evaluated_at, open=100, high=500, low=1, close=400)
    before = build_market_state("XAUUSD", evaluated_at, [], m15)
    after = build_market_state("XAUUSD", evaluated_at, [], [*m15, future])
    assert after.latest_m15_bar_at == before.latest_m15_bar_at
    assert after.regime == before.regime


def test_future_quote_is_unavailable_for_current_values():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m5 = bars("XAUUSD", Timeframe.M5, 20, start)
    evaluated_at = start + timedelta(minutes=100)
    quote = LiveMarketQuote(symbol="XAUUSD", as_of=evaluated_at + timedelta(minutes=1), bid=200, ask=201, mid=200.5, spread=1, spread_pct=.5, digits=2, age_seconds=0, status=MarketFeedStatus.LIVE)
    state = build_market_state("XAUUSD", evaluated_at, m5, [], quote=quote)
    assert state.quote.status == "future"
    assert state.spread is None
    assert state.session_context is not None
    assert state.session_context.nearest_landmark_price != 200.5


def test_stale_quote_is_exposed_but_last_causal_close_is_used():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m5 = bars("XAUUSD", Timeframe.M5, 20, start)
    evaluated_at = start + timedelta(minutes=100)
    quote = LiveMarketQuote(symbol="XAUUSD", as_of=start, bid=200, ask=201, mid=200.5, spread=1, spread_pct=.5, digits=2, age_seconds=999, status=MarketFeedStatus.STALE)
    state = build_market_state("XAUUSD", evaluated_at, m5, [], quote=quote)
    assert state.quote.status == "stale"
    assert state.spread is None
    assert state.session_context is not None


def test_neutral_regime_does_not_invent_side_aligned_landmark():
    start = datetime(2026, 9, 30, 8, tzinfo=datetime.now().astimezone().tzinfo)
    m5 = bars("XAUUSD", Timeframe.M5, 20, start, step=0)
    state = build_market_state("XAUUSD", start + timedelta(minutes=100), m5, [])
    assert state.session_context is not None
    assert state.session_context.side_aligned_distance_to_nearest_landmark is None


def test_missing_macro_is_unavailable(tmp_path):
    state = build_market_state("EURUSD", datetime(2026, 9, 30, 12, tzinfo=datetime.now().astimezone().tzinfo), [], [], macro=None)
    assert state.macro.available is False
