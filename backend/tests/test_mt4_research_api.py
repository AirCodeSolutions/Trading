from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_mt4_specs_endpoint_reads_global_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "trading_symbol_specs.csv").write_text(
        "timestamp,symbol,bid,ask,digits,contract_size,tick_size,tick_value,point,"
        "min_lot,max_lot,lot_step,stop_level,margin_required\n"
        "1,EURUSD,1.10,1.1001,5,100000,0.00001,0.9,0.00001,0.01,100,0.01,0,100\n"
        "1,BTCUSD,80000,80020,2,1,0.01,0.0087,0.01,0.01,1000,0.01,0,140\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)

    response = client.get("/api/v1/market/mt4/specs")

    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload] == ["BTCUSD", "EURUSD"]
