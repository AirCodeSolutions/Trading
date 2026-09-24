import json
from pathlib import Path

from app.domain.portfolio import BrokerDemoSnapshot


def read_broker_demo_snapshot(files_dir: Path) -> BrokerDemoSnapshot | None:
    account_values: dict[str, float | bool] | None = None
    position_ids: set[str] = set()

    for path in sorted(files_dir.glob("mt4_data_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            account = payload["account"]
            current = {
                "is_demo": str(account.get("is_demo", "0")) == "1",
                "balance": float(account["balance"]),
                "equity": float(account["equity"]),
                "margin": float(account["margin"]),
                "free_margin": float(account["freeMargin"]),
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue

        if account_values is None:
            account_values = current
        position_ids.update(_position_identities(payload.get("positions", {})))

    if account_values is None:
        return None

    return BrokerDemoSnapshot(
        is_demo=bool(account_values["is_demo"]),
        balance=float(account_values["balance"]),
        equity=float(account_values["equity"]),
        margin=float(account_values["margin"]),
        free_margin=float(account_values["free_margin"]),
        observed_positions=len(position_ids),
    )


def _position_identities(value: object) -> set[str]:
    if isinstance(value, dict):
        rows = list(value.values())
    elif isinstance(value, list):
        rows = value
    else:
        return set()

    identities: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            ticket = row.get("ticket")
            if ticket not in {None, ""}:
                identities.add(f"ticket:{ticket}")
                continue
            identities.add(
                "payload:"
                + json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            )
        else:
            identities.add(f"value:{row!r}")
    return identities
