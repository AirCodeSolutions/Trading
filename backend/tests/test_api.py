from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_is_safe_by_default() -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "paper"
    assert payload["decision_mode"] == "confirm"
    assert payload["live_trading_enabled"] is False
    assert payload["allowed_timeframes"] == ["M5", "M15"]
    assert payload["reference_capital_eur"] == 200.0
    assert payload["risk_per_trade_fraction"] == 0.01
    assert payload["absolute_max_risk_fraction"] == 0.02
    assert payload["prospective_min_trades"] == 20
    assert payload["historical_validation_min_trades"] == 40
    assert payload["historical_holdout_min_trades"] == 20


def test_ingest_and_read_m5_bar() -> None:
    bar = {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "timestamp": "2026-09-18T12:00:00Z",
        "open": 3600.0,
        "high": 3605.0,
        "low": 3598.0,
        "close": 3602.0,
        "volume": 100.0,
    }
    response = client.post("/api/v1/market/bars", json=bar)
    assert response.status_code == 201

    latest = client.get("/api/v1/market/XAUUSD/M5/latest")
    assert latest.status_code == 200
    assert latest.json()["close"] == 3602.0
