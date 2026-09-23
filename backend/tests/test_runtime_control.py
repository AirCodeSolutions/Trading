from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.runtime_control import load_runtime_drain, save_runtime_drain

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=ZoneInfo("Europe/Athens"))


def test_runtime_drain_defaults_off_and_persists_toggle(tmp_path: Path) -> None:
    path = tmp_path / "drain_state.json"

    assert load_runtime_drain(path).enabled is False

    enabled = save_runtime_drain(
        path,
        enabled=True,
        updated_at=NOW,
        reason="deployment",
    )
    assert enabled.enabled is True
    assert enabled.reason == "deployment"
    assert load_runtime_drain(path) == enabled

    disabled = save_runtime_drain(
        path,
        enabled=False,
        updated_at=NOW,
        reason="deployment complete",
    )
    assert disabled.enabled is False
    assert load_runtime_drain(path) == disabled
