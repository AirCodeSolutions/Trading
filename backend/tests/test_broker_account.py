import json
from pathlib import Path

from app.services.broker_account import read_broker_demo_snapshot


def _payload(ticket: int, symbol: str) -> dict:
    return {
        "account": {
            "is_demo": "1",
            "balance": "875000.00",
            "equity": "874900.00",
            "margin": "100.00",
            "freeMargin": "874800.00",
        },
        "positions": {
            "0": {
                "ticket": str(ticket),
                "symbol": symbol,
                "type": "SELL",
                "lots": "0.01",
            }
        },
    }


def test_broker_snapshot_aggregates_unique_positions_across_symbol_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "mt4_data_BTCUSD.json").write_text(
        json.dumps(_payload(111, "BTCUSD")),
        encoding="utf-8",
    )
    (tmp_path / "mt4_data_XAUUSD.json").write_text(
        json.dumps(_payload(222, "XAUUSD")),
        encoding="utf-8",
    )
    # Duplicate export of the BTC ticket must not be double-counted.
    (tmp_path / "mt4_data_ZZZ.json").write_text(
        json.dumps(_payload(111, "BTCUSD")),
        encoding="utf-8",
    )

    result = read_broker_demo_snapshot(tmp_path)

    assert result is not None
    assert result.observed_positions == 2
    assert result.is_demo is True
    assert result.equity == 874900.00
