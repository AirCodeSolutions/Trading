import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_live_market_endpoint_returns_prices_without_account_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "timestamp": "1789838948",
                "symbol": "BTCUSD",
                "bid": "81522.07",
                "ask": "81546.57",
                "digits": "2",
                "account": {
                    "account_number": "should-not-leak",
                    "balance": "999999",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)

    response = client.get("/api/v1/market/mt4/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["bid"] == 81522.07
    assert "account" not in payload[0]



def test_live_market_quality_endpoint_uses_mt4_spec_and_closed_bars(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "timestamp": "1789838948",
                "symbol": "BTCUSD",
                "bid": "81522.07",
                "ask": "81546.57",
                "digits": "2",
                "symbol_spec": {
                    "tick_size": "0.01",
                    "tick_value": "0.00872524",
                    "min_lot": "0.01",
                    "max_lot": "1000",
                    "lot_step": "0.01",
                    "margin_required": "140.59",
                },
            }
        ),
        encoding="utf-8",
    )
    m5_rows = [
        f"20260919,{hour:02d}:{minute:02d}:00,81000,81100,80900,{81020 + index},100"
        for index, (hour, minute) in enumerate(
            [(8, 0), (8, 5), (8, 10), (8, 15), (8, 20), (8, 25)]
        )
    ]
    m15_rows = [
        f"20260919,{hour:02d}:{minute:02d}:00,81000,81400,80800,{81100 + index * 10},300"
        for index, (hour, minute) in enumerate(
            [(7, 0), (7, 15), (7, 30), (7, 45), (8, 0), (8, 15)]
        )
    ]
    (tmp_path / "BTCUSD-M5.csv").write_text(
        "\n".join(m5_rows) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "BTCUSD-M15.csv").write_text(
        "\n".join(m15_rows) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)
    monkeypatch.setattr(settings, "session_watch_symbols", ("BTCUSD",))

    response = client.get("/api/v1/market/mt4/quality")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["symbol"] == "BTCUSD"
    assert payload[0]["required_capital_base_risk_eur"] > 0
    assert payload[0]["required_capital_max_risk_eur"] > 0
