from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.probe_review import ProbeReviewPack
from app.main import app

client = TestClient(app)


def test_probe_review_endpoint_returns_decision_support_pack(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module, "_mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(
        main_module,
        "build_probe_review_pack",
        lambda *args, **kwargs: ProbeReviewPack(
            strategy_id="BTCUSD:directional_transition",
            review_ready=False,
            reason="strategy is not SUPPORTS_REVIEW",
        ),
    )

    response = client.post(
        "/api/v1/research/probe-review",
        json={
            "strategy_id": "BTCUSD:directional_transition",
            "split": {
                "train_end": "2026-07-01T00:00:00+03:00",
                "validation_end": "2026-09-01T00:00:00+03:00",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "BTCUSD:directional_transition"
    assert payload["review_ready"] is False
    assert payload["requires_human_decision"] is True


def test_probe_review_endpoint_rejects_invalid_split() -> None:
    response = client.post(
        "/api/v1/research/probe-review",
        json={
            "strategy_id": "BTCUSD:directional_transition",
            "split": {
                "train_end": "2026-09-01T00:00:00+03:00",
                "validation_end": "2026-07-01T00:00:00+03:00",
            },
        },
    )

    assert response.status_code == 422


def test_probe_review_contract_endpoint() -> None:
    response = client.get("/api/v1/research/probe-review/contract")

    assert response.status_code == 200
    payload = response.json()
    assert payload["timezone"] == "Europe/Athens"
    assert payload["evidence_window_hours"] == 168
    assert payload["train_end"] == "2026-07-01T00:00:00+03:00"
    assert payload["validation_end"] == "2026-09-01T00:00:00+03:00"
