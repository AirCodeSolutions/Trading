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


def test_live_market_prefers_continuously_refreshed_legacy_m5_history(
    tmp_path: Path,
) -> None:
    write_quote(tmp_path / "mt4_data_XAUUSD.json", 1789775936, "XAUUSD")
    (tmp_path / "XAUUSD-M5.csv").write_text(
        "20260918,23:45:00,4380.84,4380.84,4376.82,4377.89,390\n"
        "20260918,23:50:00,4377.63,4378.40,4376.36,4378.28,313\n",
        encoding="utf-8",
    )
    (tmp_path / "mt4_research_bars_XAUUSD_M5.csv").write_text(
        "timestamp,open,high,low,close,volume\n"
        "1789634100,4294.88,4297.09,4292.56,4296.78,767\n"
        "1789634400,4296.95,4298.06,4294.37,4296.99,724\n",
        encoding="utf-8",
    )
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quote = read_live_market_quotes(tmp_path, now)[0]

    assert quote.last_closed_m5_at is not None
    assert quote.last_closed_m5_at.isoformat() == "2026-09-18T23:50:00+03:00"
    assert quote.recent_m5_closes == [4377.89, 4378.28]


def test_multi_market_exporter_csv_adds_live_quote(tmp_path: Path) -> None:
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1789838948,GBPUSD,1.34000,1.34012,5,100000,0.00001,0.87,0.00001,0.01,100,0.01,0,100\n",
        encoding="utf-8",
    )
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quotes = read_live_market_quotes(tmp_path, now)

    assert len(quotes) == 1
    quote = quotes[0]
    assert quote.symbol == "GBPUSD"
    assert quote.bid == 1.34
    assert quote.ask == 1.34012
    assert quote.status == MarketFeedStatus.LIVE


def test_newest_quote_wins_between_json_and_multi_market_exporter(
    tmp_path: Path,
) -> None:
    write_quote(tmp_path / "mt4_data_BTCUSD.json", 1789838948)
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1789839000,BTCUSD,81600,81624.5,2,1,0.01,0.0087,0.01,0.01,10,0.01,0,140\n",
        encoding="utf-8",
    )
    now = datetime(2026, 9, 19, 17, 31, 0, tzinfo=TZ)

    quote = read_live_market_quotes(tmp_path, now)[0]

    assert quote.bid == 81600
    assert quote.ask == 81624.5


def test_live_quote_filter_excludes_out_of_scope_symbols(tmp_path: Path) -> None:
    write_quote(tmp_path / "mt4_data_EURUSD.json", 1789838948, "EURUSD")
    write_quote(tmp_path / "mt4_data_US500Cash.json", 1789838948, "US500Cash")
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quotes = read_live_market_quotes(tmp_path, now, symbols=("EURUSD",))

    assert [quote.symbol for quote in quotes] == ["EURUSD"]


def test_symbol_scoped_demo_bridge_snapshot_adds_live_quote(tmp_path: Path) -> None:
    (tmp_path / "trading_demo_spec_GBPUSD.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1789838948,GBPUSD,1.34000,1.34011,5,100000,0.00001,0.87,0.00001,0.01,100,0.01,0,100\n",
        encoding="utf-8",
    )
    now = datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ)

    quotes = read_live_market_quotes(tmp_path, now, symbols=("GBPUSD",))

    assert len(quotes) == 1
    assert quotes[0].symbol == "GBPUSD"
    assert quotes[0].bid == 1.34
    assert quotes[0].ask == 1.34011
    assert quotes[0].status == MarketFeedStatus.LIVE
