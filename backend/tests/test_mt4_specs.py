import json
from pathlib import Path

from app.services.mt4_specs import (
    get_mt4_symbol_spec,
    list_mt4_symbol_specs,
    read_symbol_snapshot,
)


def test_reads_valid_symbol_snapshot_and_skips_invalid_rows(tmp_path: Path) -> None:
    path = tmp_path / "trading_symbol_specs.csv"
    path.write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,"
        "min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1,EURUSD,1.10,1.1001,5,100000,0.00001,0.9,0.00001,0.01,100,0.01,0,100\n"
        "1,BAD,0,0,2,1,0,0,0.01,0,0,0,0,0\n",
        encoding="utf-8",
    )

    specs = read_symbol_snapshot(path)

    assert set(specs) == {"EURUSD"}
    assert specs["EURUSD"].min_lot == 0.01


def test_json_fallback_supplies_existing_mt4_bridge_symbols(tmp_path: Path) -> None:
    payload = {
        "symbol": "BTCUSD",
        "bid": "80000",
        "ask": "80020",
        "symbol_spec": {
            "tick_size": "0.01",
            "tick_value": "0.0087",
            "min_lot": "0.01",
            "max_lot": "1000",
            "lot_step": "0.01",
            "margin_required": "140",
        },
    }
    (tmp_path / "mt4_data_BTCUSD.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    spec = get_mt4_symbol_spec(tmp_path, "btcusd")

    assert spec is not None
    assert spec.symbol == "BTCUSD"
    assert spec.spread == 20


def test_snapshot_takes_precedence_over_bridge_json(tmp_path: Path) -> None:
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,"
        "min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1,XAUUSD,4300,4300.2,2,100,0.01,1,0.01,0.01,100,0.01,0,380\n",
        encoding="utf-8",
    )
    payload = {
        "symbol": "XAUUSD",
        "bid": "4200",
        "ask": "4201",
        "symbol_spec": {
            "tick_size": "0.01",
            "tick_value": "1",
            "min_lot": "0.01",
            "max_lot": "100",
            "lot_step": "0.01",
            "margin_required": "380",
        },
    }
    (tmp_path / "mt4_data_XAUUSD.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    specs = list_mt4_symbol_specs(tmp_path)

    assert specs["XAUUSD"].spread == 0.2
