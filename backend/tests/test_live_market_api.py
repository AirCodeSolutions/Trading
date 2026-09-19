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
