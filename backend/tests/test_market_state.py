import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pytest import approx

from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.market import MarketBar, Timeframe
from app.domain.market_state import MarketStateFreshness
from app.services.market_state import (
    _m5_features,
    build_market_state,
    build_market_state_macro_context,
)
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


def fixed_close_bars(symbol: str, closes: list[float], ranges: list[float] | None = None) -> list[MarketBar]:
    start = datetime(2026, 9, 30, 8, tzinfo=ZoneInfo("Europe/Athens"))
    widths = ranges or [0.2] * len(closes)
    result = []
    previous = closes[0]
    for index, close in enumerate(closes):
        width = widths[index]
        result.append(MarketBar(symbol=symbol, timeframe=Timeframe.M5, timestamp=start + timedelta(minutes=index * 5), open=previous, high=max(previous, close) + width / 2, low=min(previous, close) - width / 2, close=close))
        previous = close
    return result


def m15_regime_bars(kind: str) -> list[MarketBar]:
    start = datetime(2026, 9, 30, 8, tzinfo=ZoneInfo("Europe/Athens"))
    result = []
    price = 100.0
    for index in range(55):
        if kind == "directional":
            close = price + 0.2
            width = 0.25
        elif kind == "dead":
            close = price + (0.001 if index % 2 else -0.001)
            width = 1.0 if index < 50 else 0.01
        else:
            close = price + (0.15 if index % 2 else -0.15)
            width = 0.3
        result.append(MarketBar(symbol="XAUUSD", timeframe=Timeframe.M15, timestamp=start + timedelta(minutes=index * 15), open=price, high=max(price, close) + width / 2, low=min(price, close) - width / 2, close=close))
        price = close
    return result


def test_m15_regime_categories_are_deterministic():
    assert build_market_state("XAUUSD", m15_regime_bars("directional")[-1].timestamp + timedelta(minutes=15), [], m15_regime_bars("directional")).regime == "directional_expansion"
    assert build_market_state("XAUUSD", m15_regime_bars("balanced")[-1].timestamp + timedelta(minutes=15), [], m15_regime_bars("balanced")).regime == "balanced_auction"
    assert build_market_state("XAUUSD", m15_regime_bars("dead")[-1].timestamp + timedelta(minutes=15), [], m15_regime_bars("dead")).regime == "dead"


def test_m5_persistence_and_momentum_have_signed_expected_values():
    positive = _m5_features(fixed_close_bars("XAUUSD", [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7]), 0.2)
    negative = _m5_features(fixed_close_bars("XAUUSD", [100, 99.9, 99.8, 99.7, 99.6, 99.5, 99.4, 99.3]), 0.2)
    assert positive["persistence"] == approx(1.0) and positive["momentum"] == approx(1.5)
    assert negative["persistence"] == approx(-1.0) and negative["momentum"] == approx(-1.5)


def test_m5_acceleration_deceleration_and_range_expansion_are_numeric():
    accelerating = _m5_features(fixed_close_bars("XAUUSD", [100, 100.05, 100.1, 100.15, 100.25, 100.35, 100.45, 100.55], [0.2] * 8), 0.2)
    decelerating = _m5_features(fixed_close_bars("XAUUSD", [100, 100.15, 100.3, 100.45, 100.5, 100.55, 100.6, 100.65], [0.2] * 8), 0.2)
    expanding = _m5_features(fixed_close_bars("XAUUSD", [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7], [0.2] * 7 + [0.4]), 0.2)
    compressing = _m5_features(fixed_close_bars("XAUUSD", [100, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7], [0.2] * 7 + [0.1]), 0.2)
    assert accelerating["acceleration"] == approx(0.75)
    assert decelerating["acceleration"] == approx(-1.5)
    assert expanding["expansion"] == approx(1.75)
    assert compressing["expansion"] == approx(0.70)


def test_m5_extension_and_exhaustion_use_the_documented_formula():
    low = _m5_features(fixed_close_bars("XAUUSD", [100, 100.01, 100.02, 100.03, 100.04, 100.05, 100.06, 100.07]), 0.2)
    high = _m5_features(fixed_close_bars("XAUUSD", [100, 100.1, 100.0, 100.1, 100.0, 100.2, 100.0, 100.2]), 0.2)
    assert low["extension"] == approx(0.35)
    assert high["extension"] == approx(1.0)
    assert high["exhaustion"] == approx(2 / 3)


def test_quote_states_and_causal_timestamps_are_explicit():
    start = datetime(2026, 9, 30, 10, tzinfo=ZoneInfo("Europe/Athens"))
    m5 = bars("XAUUSD", Timeframe.M5, 1, start)
    m15 = bars("XAUUSD", Timeframe.M15, 1, start)
    evaluated_at = start + timedelta(minutes=15)
    fresh = LiveMarketQuote(symbol="XAUUSD", as_of=evaluated_at, bid=100, ask=101, mid=100.5, spread=1, spread_pct=1, digits=2, age_seconds=0, status=MarketFeedStatus.LIVE)
    state = build_market_state("XAUUSD", evaluated_at, m5, m15, quote=fresh)
    assert state.quote.available is True and state.quote.status == "fresh" and state.quote.age_seconds == 0
    assert state.latest_m5_bar_at == start and state.latest_m5_closed_at == start + timedelta(minutes=5)
    assert state.latest_m15_bar_at == start and state.latest_m15_closed_at == start + timedelta(minutes=15)


def test_macro_context_availability_contract(tmp_path):
    now = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Europe/Athens"))
    missing = build_market_state_macro_context(tmp_path / "missing.json", now)
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("invalid", encoding="utf-8")
    invalid = build_market_state_macro_context(invalid_path, now)
    valid_path = tmp_path / "valid.json"
    valid_path.write_text("[]", encoding="utf-8")
    valid = build_market_state_macro_context(valid_path, now)
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps([{
        "event_id": "test", "name": "CPI", "start_at": now.isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(), "impact": "high",
        "currencies": ["USD"], "source": "test",
    }]), encoding="utf-8")
    blocked = build_market_state_macro_context(event_path, now)
    assert not missing.available and not invalid.available
    assert valid.available and valid.blocked is False
    assert blocked.available and blocked.blocked is True


def test_market_state_api_exposes_five_assets_without_execution_authority(monkeypatch, tmp_path):
    from app import main
    monkeypatch.setattr(main, "_mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(main, "read_live_market_quotes", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "load_closed_market_bars", lambda *args, **kwargs: [])
    response = TestClient(main.app).get("/api/v1/market-state/v2")
    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload] == ["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"]
    assert all(not any(key in item for key in ("order", "command", "sizing", "execution_proposal")) for item in payload)


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
    assert state.quote.available is False
    assert state.quote.status == "unavailable"

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
