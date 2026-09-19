import json
from datetime import datetime
from pathlib import Path

from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.market import Timeframe
from app.services.mt4_csv import mt4_epoch_to_server_datetime
from app.services.mt4_live_bars import read_closed_bar_snapshot


LIVE_MAX_AGE_SECONDS = 120
SPARKLINE_BARS = 48


def read_live_market_quotes(
    files_dir: Path,
    now: datetime,
) -> list[LiveMarketQuote]:
    quotes: list[LiveMarketQuote] = []
    for path in sorted(files_dir.glob("mt4_data_*.json")):
        quote = _read_quote(path, files_dir, now)
        if quote is not None:
            quotes.append(quote)
    return quotes


def _read_quote(
    path: Path,
    files_dir: Path,
    now: datetime,
) -> LiveMarketQuote | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        symbol = str(payload["symbol"]).upper()
        timestamp = mt4_epoch_to_server_datetime(int(payload["timestamp"]))
        bid = float(payload["bid"])
        ask = float(payload["ask"])
        digits = int(payload["digits"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if bid <= 0 or ask <= 0 or ask < bid:
        return None

    age_seconds = max(0.0, (now - timestamp).total_seconds())
    status = (
        MarketFeedStatus.LIVE
        if age_seconds <= LIVE_MAX_AGE_SECONDS
        else MarketFeedStatus.STALE
    )
    mid = (bid + ask) / 2
    spread = ask - bid

    closes: list[float] = []
    last_closed_m5_at = None
    recent_change_pct = None
    bars_path = files_dir / f"mt4_bars_{symbol}_M5.json"
    if bars_path.is_file():
        try:
            bars = read_closed_bar_snapshot(bars_path, symbol, Timeframe.M5)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            bars = []
        if bars:
            recent = bars[-SPARKLINE_BARS:]
            closes = [bar.close for bar in recent]
            last_closed_m5_at = bars[-1].timestamp
            if len(closes) >= 2 and closes[0] > 0:
                recent_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100

    return LiveMarketQuote(
        symbol=symbol,
        as_of=timestamp,
        bid=bid,
        ask=ask,
        mid=mid,
        spread=spread,
        spread_pct=(spread / mid) * 100,
        digits=digits,
        age_seconds=age_seconds,
        status=status,
        last_closed_m5_at=last_closed_m5_at,
        recent_change_pct=recent_change_pct,
        recent_m5_closes=closes,
    )
