from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_shadow_collect_returns_404_without_mt4_snapshots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path / "ledger")

    response = client.post("/api/v1/shadow/mt4/btc/break-retest/collect")

    assert response.status_code == 404
