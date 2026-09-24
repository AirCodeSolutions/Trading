from pathlib import Path

from app.domain.runtime_capital import (
    RuntimeCapitalSnapshot,
    RuntimeCapitalSource,
)
from app.services.broker_account import read_broker_demo_snapshot


def resolve_demo_sizing_capital(files_dir: Path) -> RuntimeCapitalSnapshot:
    broker = read_broker_demo_snapshot(files_dir)
    if broker is None:
        return RuntimeCapitalSnapshot(
            source=RuntimeCapitalSource.UNAVAILABLE,
            is_demo=None,
        )
    if not broker.is_demo:
        return RuntimeCapitalSnapshot(
            source=RuntimeCapitalSource.UNAVAILABLE,
            is_demo=False,
        )
    if broker.equity > 0:
        return RuntimeCapitalSnapshot(
            capital_eur=broker.equity,
            source=RuntimeCapitalSource.BROKER_EQUITY,
            is_demo=True,
        )
    if broker.balance > 0:
        return RuntimeCapitalSnapshot(
            capital_eur=broker.balance,
            source=RuntimeCapitalSource.BROKER_BALANCE,
            is_demo=True,
        )
    return RuntimeCapitalSnapshot(
        source=RuntimeCapitalSource.UNAVAILABLE,
        is_demo=True,
    )
