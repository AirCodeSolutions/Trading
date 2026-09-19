import json
from pathlib import Path

from app.domain.portfolio import BrokerDemoSnapshot


def read_broker_demo_snapshot(files_dir: Path) -> BrokerDemoSnapshot | None:
    for path in sorted(files_dir.glob("mt4_data_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            account = payload["account"]
            positions = payload.get("positions", {})
            return BrokerDemoSnapshot(
                is_demo=str(account.get("is_demo", "0")) == "1",
                balance=float(account["balance"]),
                equity=float(account["equity"]),
                margin=float(account["margin"]),
                free_margin=float(account["freeMargin"]),
                observed_positions=_position_count(positions),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def _position_count(value: object) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0
