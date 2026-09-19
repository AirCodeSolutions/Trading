import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.live_market import MarketFeedStatus
from app.services.mt4_live_quotes import read_live_market_quotes


TZ = ZoneInfo("Europe/Athens")


def write_quote(path: Path, timestamp: int, symbol: str = "BTCUSD") -> None:
    path.write_text(
        json.dumps(
            {
                "timestamp": str(timestamp),
                "symbol": symbol,
                "bid": "81522.07",
                "ask": "81546.57",
                "digits": "2",
                "account": {"account_number": "should-not-leak"},
            }
        ),
        encoding="utf-8",
    )


def test_live_quote_contains_price_without_account_data(tmp_path: Path) -> None:
    # MT4 epoch encodes the server wall clock 2026-09-19 17:29:08.
    write_quote(tmp_path / "mt4_data_BTCUSD.json", 1789838948)
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quotes = read_live_market_quotes(tmp_path, now)

    assert len(quotes) == 1
    quote = quotes[0]
    assert quote.symbol == "BTCUSD"
    assert quote.bid == 81522.07
    assert quote.ask == 81546.57
    assert quote.status == MarketFeedStatus.LIVE
    assert "account" not in quote.model_dump()


def test_old_quote_is_marked_stale(tmp_path: Path) -> None:
    write_quote(tmp_path / "mt4_data_XAUUSD.json", 1789775936, "XAUUSD")
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quote = read_live_market_quotes(tmp_path, now)[0]

    assert quote.status == MarketFeedStatus.STALE
    assert quote.age_seconds > timedelta(hours=12).total_seconds()
