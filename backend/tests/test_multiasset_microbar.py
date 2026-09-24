import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.xau_microbar import (
    SUPPORTED_SYMBOLS,
    load_all_market_microbar_summaries,
    microbar_ledger_file,
    sample_market_microbar_once,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 24, 10, 0, tzinfo=TZ)


def _server_epoch(at: datetime) -> int:
    return int(at.replace(tzinfo=UTC).timestamp())


def _write_quote(
    files_dir: Path,
    symbol: str,
    at: datetime,
    bid: float,
    ask: float,
) -> None:
    path = files_dir / f"trading_demo_spec_{symbol}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "symbol",
                "bid",
                "ask",
                "digits",
                "contract_size",
                "tick_size",
                "tick_value",
                "point",
                "min_lot",
                "max_lot",
                "lot_step",
                "stop_level",
                "margin_required",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": _server_epoch(at),
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "digits": 5,
                "contract_size": 1,
                "tick_size": 0.00001,
                "tick_value": 1,
                "point": 0.00001,
                "min_lot": 0.01,
                "max_lot": 10000,
                "lot_step": 0.01,
                "stop_level": 0,
                "margin_required": 100,
            }
        )


def test_multiasset_sampler_keeps_ledgers_isolated(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    _write_quote(
        files_dir,
        "BTCUSD",
        START + timedelta(seconds=1),
        83800.0,
        83824.0,
    )
    _write_quote(
        files_dir,
        "EURUSD",
        START + timedelta(seconds=1),
        1.13700,
        1.13708,
    )

    btc = sample_market_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
        symbol="BTCUSD",
    )
    eur = sample_market_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(seconds=2),
        symbol="EURUSD",
    )

    assert btc.symbol == "BTCUSD"
    assert eur.symbol == "EURUSD"
    assert btc.total_quote_samples == 1
    assert eur.total_quote_samples == 1
    assert btc.current_bar is not None
    assert eur.current_bar is not None
    assert btc.current_bar.mid_open > 80_000
    assert eur.current_bar.mid_open < 2
    assert not (runtime_dir / microbar_ledger_file("BTCUSD")).exists()
    assert not (runtime_dir / microbar_ledger_file("EURUSD")).exists()

    _write_quote(
        files_dir,
        "BTCUSD",
        START + timedelta(minutes=1, seconds=1),
        83810.0,
        83834.0,
    )
    btc_next = sample_market_microbar_once(
        files_dir,
        runtime_dir,
        START + timedelta(minutes=1, seconds=2),
        symbol="BTCUSD",
    )

    assert btc_next.closed_bars == 1
    assert (runtime_dir / microbar_ledger_file("BTCUSD")).is_file()
    assert not (runtime_dir / microbar_ledger_file("EURUSD")).exists()


def test_all_market_microbar_summaries_cover_five_assets(
    tmp_path: Path,
) -> None:
    summaries = load_all_market_microbar_summaries(
        tmp_path,
        now=START,
    )

    assert [item.symbol for item in summaries] == list(SUPPORTED_SYMBOLS)
    assert all(item.closed_bars == 0 for item in summaries)
    assert all(item.healthy is False for item in summaries)


def test_multiasset_microbar_endpoint_lists_five_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)

    response = TestClient(app).get("/api/v1/research/microbars")

    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload] == list(SUPPORTED_SYMBOLS)
    assert all(item["timeframe"] == "M1" for item in payload)
