from pathlib import Path

import pytest

from app.shadow_worker import _acquire_worker_lock


def test_shadow_worker_lock_is_singleton(tmp_path: Path) -> None:
    lock_path = tmp_path / "worker.lock"
    first = _acquire_worker_lock(lock_path)
    try:
        with pytest.raises(SystemExit, match="already running"):
            _acquire_worker_lock(lock_path)
    finally:
        first.close()

    second = _acquire_worker_lock(lock_path)
    second.close()


def test_start_script_refuses_second_worker_if_old_pid_does_not_stop() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "ops" / "start_trading.sh").read_text(
        encoding="utf-8"
    )

    assert "Refusing to start a second shadow worker" in source
    assert 'kill -0 "$old_worker_pid"' in source
