import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.market_universe import build_market_universe

TZ = ZoneInfo("Europe/Athens")


def test_universe_includes_history_only_market_without_fake_bid_ask(
    tmp_path: Path,
) -> None:
    (tmp_path / "GBPUSD-M5.csv").write_text(
        "20260918,23:50:00,1.20,1.21,1.19,1.205,100\n",
        encoding="utf-8",
    )
    (tmp_path / "GBPUSD-M15.csv").write_text(
        "20260918,23:45:00,1.20,1.21,1.19,1.205,300\n",
        encoding="utf-8",
    )

    assets = build_market_universe(
        tmp_path,
        datetime(2026, 9, 19, 17, 0, tzinfo=TZ),
    )

    assert len(assets) == 1
    asset = assets[0]
    assert asset.symbol == "GBPUSD"
    assert asset.price == 1.205
    assert asset.price_source == "closed_m5"
    assert asset.bid is None
    assert asset.ask is None
    assert asset.research_ready is True
    assert asset.broker_spec_ready is False
    assert asset.paper_ready is False


def test_universe_marks_quote_spec_and_history_as_paper_ready(
    tmp_path: Path,
) -> None:
    (tmp_path / "EURUSD-M5.csv").write_text(
        "20260919,16:55:00,1.14,1.15,1.13,1.145,100\n",
        encoding="utf-8",
    )
    (tmp_path / "EURUSD-M15.csv").write_text(
        "20260919,16:45:00,1.14,1.15,1.13,1.145,300\n",
        encoding="utf-8",
    )
    (tmp_path / "mt4_data_EURUSD.json").write_text(
        json.dumps(
            {
                "timestamp": "1789837200",
                "symbol": "EURUSD",
                "bid": "1.1450",
                "ask": "1.1451",
                "digits": "5",
                "symbol_spec": {
                    "tick_size": "0.00001",
                    "tick_value": "0.87",
                    "min_lot": "0.01",
                    "max_lot": "100",
                    "lot_step": "0.01",
                    "margin_required": "100",
                },
            }
        ),
        encoding="utf-8",
    )

    assets = build_market_universe(
        tmp_path,
        datetime(2026, 9, 19, 17, 1, tzinfo=TZ),
    )

    asset = assets[0]
    assert asset.price_source == "broker_quote"
    assert asset.broker_spec_ready is True
    assert asset.research_ready is True
    assert asset.paper_ready is True


def test_universe_becomes_paper_ready_from_single_exporter_snapshot(
    tmp_path: Path,
) -> None:
    (tmp_path / "GBPUSD-M5.csv").write_text(
        "20260919,17:20:00,1.339,1.341,1.338,1.340,100\n",
        encoding="utf-8",
    )
    (tmp_path / "GBPUSD-M15.csv").write_text(
        "20260919,17:15:00,1.339,1.341,1.338,1.340,300\n",
        encoding="utf-8",
    )
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1789838948,GBPUSD,1.34000,1.34012,5,100000,0.00001,0.87,0.00001,0.01,100,0.01,0,100\n",
        encoding="utf-8",
    )

    assets = build_market_universe(
        tmp_path,
        datetime(2026, 9, 19, 17, 30, 0, tzinfo=TZ),
    )

    asset = assets[0]
    assert asset.symbol == "GBPUSD"
    assert asset.price_source == "broker_quote"
    assert asset.quote_live is True
    assert asset.broker_spec_ready is True
    assert asset.paper_ready is True


def test_universe_scope_excludes_abandoned_history(tmp_path: Path) -> None:
    for symbol in ("EURUSD", "US500Cash"):
        (tmp_path / f"{symbol}-M5.csv").write_text(
            "20260919,16:55:00,1.14,1.15,1.13,1.145,100\n",
            encoding="utf-8",
        )
        (tmp_path / f"{symbol}-M15.csv").write_text(
            "20260919,16:45:00,1.14,1.15,1.13,1.145,300\n",
            encoding="utf-8",
        )
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1789838948,EURUSD,1.1450,1.1451,5,100000,0.00001,0.87,0.00001,0.01,100,0.01,0,100\n"
        "1789838948,US500Cash,6500,6501,1,1,0.1,0.1,0.1,0.01,100,0.01,0,100\n",
        encoding="utf-8",
    )

    assets = build_market_universe(
        tmp_path,
        datetime(2026, 9, 19, 17, 1, tzinfo=TZ),
        symbols=("EURUSD",),
    )

    assert [asset.symbol for asset in assets] == ["EURUSD"]
