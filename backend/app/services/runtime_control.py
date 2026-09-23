from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.domain.runtime_control import RuntimeDrainState

DRAIN_FILE = "drain_state.json"


def load_runtime_drain(path: Path) -> RuntimeDrainState:
    if not path.is_file():
        return RuntimeDrainState()
    try:
        return RuntimeDrainState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return RuntimeDrainState()


def save_runtime_drain(
    path: Path,
    *,
    enabled: bool,
    updated_at: datetime,
    reason: str = "",
) -> RuntimeDrainState:
    state = RuntimeDrainState(
        enabled=enabled,
        updated_at=updated_at,
        reason=reason.strip(),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return state
