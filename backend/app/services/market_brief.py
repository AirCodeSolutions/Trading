from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.domain.macro import MacroEvent, MacroImpact
from app.domain.market import Timeframe
from app.domain.market_brief import DailyMarketBrief, MarketBriefAsset, MarketBriefEvent
from app.domain.trading import Side
from app.services.macro_gate import active_macro_blackouts, load_macro_events
from app.services.market_session import MarketSessionStatus, market_session_status
from app.services.mt4_csv import _server_timezone
from app.services.mt4_live_quotes import read_live_market_quotes
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.opportunity_strategies import _atr_series
from app.services.regime import classify_regime
from app.services.session_landmarks import build_session_landmark_context

_ASSET_CURRENCIES = {
    "BTCUSD": ("USD",),
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "XAUUSD": ("USD",),
    "XAGUSD": ("USD",),
}
_ASSETS = ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD")


def build_daily_market_brief(files_dir: Path, *, now: datetime) -> DailyMarketBrief:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("market brief requires timezone-aware now")
    now_server = now.astimezone(_server_timezone())
    quotes = {quote.symbol: quote for quote in read_live_market_quotes(files_dir, now_server, symbols=_ASSETS)}
    events = load_macro_events(settings.macro_events_path)
    assets = [
        _build_asset(files_dir, symbol, now_server, quotes.get(symbol), events)
        for symbol in _ASSETS
    ]
    upcoming = _upcoming_events(events, now_server)
    warnings = sorted({warning for asset in assets for warning in asset.warnings})
    return DailyMarketBrief(
        generated_at=now_server,
        timezone=settings.mt4_server_timezone,
        assets=assets,
        upcoming_events=upcoming,
        global_warnings=warnings,
        data_freshness={
            "quote_max_age_seconds": 120,
            "closed_bar_contract": "M5/M15 fully closed before generated_at",
        },
    )


def format_time_until(minutes: float) -> str:
    if minutes < 60:
        return f"{max(0, round(minutes))} min"
    total_hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)
    if minutes < 24 * 60:
        return f"{total_hours} h {remaining_minutes:02d}"
    days, hours = divmod(total_hours, 24)
    return f"{days} j {hours} h"


def _build_asset(files_dir, symbol, now, quote, events):
    session_state = market_session_status(symbol, now)
    # 600 M5 bars cover the previous-day/session landmarks and the current
    # operational context; 250 M15 bars cover the regime replay warmup.
    bars_m5 = load_recent_closed_market_bars(files_dir, symbol, Timeframe.M5, now, limit=600)
    bars_m15 = load_recent_closed_market_bars(files_dir, symbol, Timeframe.M15, now, limit=250)
    warnings: list[str] = []
    if quote is None or quote.status.value != "live":
        warnings.append("data issue: quote unavailable or stale")
    if len(bars_m5) < 30 or len(bars_m15) < 50:
        warnings.append("data issue: insufficient closed bars")
    price = quote.mid if quote else (bars_m5[-1].close if bars_m5 else None)
    atr_m5 = _atr_series(bars_m5)[-1] if bars_m5 else None
    regime = classify_regime(bars_m15) if bars_m15 else None
    atr_m15 = regime.atr if regime else None
    context = build_session_landmark_context(
        bars_m5, now, price, Side.BUY,
        atr_m5=atr_m5, atr_m15=atr_m15,
    ) if price is not None else None
    relevant = [event for event in events if set(_ASSET_CURRENCIES[symbol]) & {c.upper() for c in event.currencies}]
    active = [event for currency in _ASSET_CURRENCIES[symbol] for event in active_macro_blackouts(relevant, now, currency=currency)]
    next_event = min((event for event in relevant if event.end_at + timedelta(minutes=event.post_block_minutes) > now), key=lambda event: event.start_at, default=None)
    minutes = (next_event.start_at - now).total_seconds() / 60 if next_event else None
    if active:
        warnings.append("macro block active")
    elif next_event and minutes is not None and minutes < 60:
        warnings.append("macro watch")
    if session_state == MarketSessionStatus.CLOSED:
        warnings.append("market closed")
    if quote and quote.spread > 0 and atr_m5:
        spread_atr_m5 = quote.spread / atr_m5
    else:
        spread_atr_m5 = None
    spread_atr_m15 = quote.spread / atr_m15 if quote and quote.spread > 0 and atr_m15 else None
    readiness = "READY" if session_state == MarketSessionStatus.OPEN and quote and quote.status.value == "live" and len(bars_m5) >= 30 and len(bars_m15) >= 50 else "MARKET CLOSED" if session_state == MarketSessionStatus.CLOSED else "DATA ISSUE"
    return MarketBriefAsset(
        symbol=symbol, as_of=quote.as_of if quote else now, bid=quote.bid if quote else None, ask=quote.ask if quote else None,
        spread=quote.spread if quote else None, spread_atr_m5=spread_atr_m5, spread_atr_m15=spread_atr_m15,
        session=context.active_session if context else None, market_session_state=session_state.value,
        regime=regime.regime.value if regime else None, regime_direction=regime.direction if regime else None,
        volatility_percentile=_volatility_percentile(bars_m15), atr_m5=atr_m5, atr_m15=atr_m15,
        previous_day_high=context.previous_day_high if context else None, previous_day_low=context.previous_day_low if context else None,
        asia_high=context.asia_high if context else None, asia_low=context.asia_low if context else None,
        london_high_so_far=context.london_high_so_far if context else None, london_low_so_far=context.london_low_so_far if context else None,
        us_high_so_far=context.us_high_so_far if context else None, us_low_so_far=context.us_low_so_far if context else None,
        nearest_landmark=context.nearest_landmark_type if context else None, nearest_landmark_price=context.nearest_landmark_price if context else None,
        nearest_distance=context.nearest_landmark_distance if context else None, nearest_distance_atr_m5=context.nearest_landmark_distance_atr_m5 if context else None,
        nearest_distance_atr_m15=context.nearest_landmark_distance_atr_m15 if context else None,
        active_session_range_position=context.active_session_position if context else None,
        next_event=next_event, next_event_time_until_minutes=minutes, next_event_time_until_display=format_time_until(minutes) if minutes is not None else None,
        next_event_relevance="high" if next_event and next_event.impact == MacroImpact.HIGH else "medium" if next_event else None,
        macro_blocked=bool(active), readiness=readiness, quote_age_seconds=quote.age_seconds if quote else None,
        m5_age_minutes=(now - bars_m5[-1].timestamp - timedelta(minutes=5)).total_seconds() / 60 if bars_m5 else None,
        warnings=warnings,
    )


def _upcoming_events(events: list[MacroEvent], now: datetime) -> list[MarketBriefEvent]:
    result = []
    for event in events:
        minutes = (event.start_at - now).total_seconds() / 60
        if event.end_at + timedelta(minutes=event.post_block_minutes) <= now:
            continue
        affected = [symbol for symbol, currencies in _ASSET_CURRENCIES.items() if set(currencies) & {c.upper() for c in event.currencies}]
        blocked = any(active_macro_blackouts(events, now, currency=currency) for currency in {c for symbol in affected for c in _ASSET_CURRENCIES[symbol]})
        result.append(MarketBriefEvent(event=event, time_until_minutes=minutes, time_until_display=format_time_until(minutes), affected_assets=affected, macro_blocked_now=blocked))
    return sorted(result, key=lambda item: item.event.start_at)[:12]


def _volatility_percentile(bars) -> float | None:
    if len(bars) < 20:
        return None
    ranges = [bar.high - bar.low for bar in bars[-96:]]
    current = ranges[-1]
    return sum(value <= current for value in ranges) / len(ranges)
