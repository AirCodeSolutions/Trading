from datetime import UTC

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
    assert payload["demo_collection_enabled"] is False
    assert payload["demo_execution_bridge_enabled"] is False
    assert payload["allowed_timeframes"] == ["M5", "M15"]
    assert payload["reference_capital_eur"] == 400.0
    assert payload["risk_per_trade_fraction"] == 0.01
    assert payload["max_lots_per_trade"] == 5.0
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


def test_paired_economic_contracts_endpoint_is_research_only() -> None:
    response = client.get(
        "/api/v1/research/paired-economic-contracts/xau-structural-displacement"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["family_id"] == "XAUUSD:structural_displacement_sequence"
    assert payload["broker_authority"] is False
    assert payload["human_review_required"] is True
    assert payload["champion"]["contract_id"] == "xau_sd_target_1r_v1"
    assert payload["challenger"]["contract_id"] == "xau_sd_target_1_5r_v2"


def test_authority_regret_endpoint_is_descriptive() -> None:
    response = client.get("/api/v1/research/authority-regret?hours=24")
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 24
    assert "winners_missed" in payload
    assert "losses_avoided" in payload
    assert "guard_blocked_total_r" in payload
    assert "cost_basis" in payload


def test_authority_regret_endpoint_rejects_invalid_window() -> None:
    response = client.get("/api/v1/research/authority-regret?hours=0")
    assert response.status_code == 422


def _runtime_admission_report():
    from datetime import datetime

    from app.domain.runtime_admission_refresh import RuntimeAdmissionRefreshReport

    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    return RuntimeAdmissionRefreshReport(
        generated_at=now,
        applied=False,
        apply_allowed=True,
        capital_eur=866312.61,
        capital_source="broker_equity",
        active_assets=["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"],
        train_end=now,
        validation_end=now,
        evaluated_results=33,
        drain_enabled=True,
        book_flat=True,
        paper_open_positions=0,
        bridge_open_positions=0,
        pending_open_command=False,
        pending_close_command=False,
        added=1,
        removed=0,
        changed=2,
        unchanged=30,
        registry_path="/tmp/strategy_admissions.json",
        receipt_path="/tmp/runtime_admission_refresh_receipt.json",
    )


def test_runtime_admission_preview_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "app.main.preview_runtime_admissions",
        lambda *args, **kwargs: _runtime_admission_report(),
    )
    response = client.post("/api/v1/research/runtime-admissions/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is False
    assert payload["apply_allowed"] is True
    assert payload["changed"] == 2


def test_runtime_admission_refresh_endpoint_returns_controlled_report(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)
    report = _runtime_admission_report().model_copy(update={"applied": True})
    monkeypatch.setattr(
        "app.main.refresh_runtime_admissions",
        lambda *args, **kwargs: report,
    )
    response = client.post("/api/v1/research/runtime-admissions/refresh")
    assert response.status_code == 200
    assert response.json()["applied"] is True


def test_runtime_admission_refresh_endpoint_returns_409_when_guard_blocks(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    def blocked(*args, **kwargs):
        raise ValueError("runtime admission refresh apply blocked: runtime drain must be ON")

    monkeypatch.setattr("app.main.refresh_runtime_admissions", blocked)
    response = client.post("/api/v1/research/runtime-admissions/refresh")
    assert response.status_code == 409
    assert "drain must be ON" in response.json()["detail"]
