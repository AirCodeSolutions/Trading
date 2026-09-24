from pathlib import Path

import pytest

from app.xau_microbar_worker import _acquire_worker_lock


def test_xau_microbar_worker_lock_is_singleton(tmp_path: Path) -> None:
    lock_path = tmp_path / "xau-microbar-worker.lock"
    first = _acquire_worker_lock(lock_path)
    try:
        with pytest.raises(SystemExit, match="already running"):
            _acquire_worker_lock(lock_path)
    finally:
        first.close()

    second = _acquire_worker_lock(lock_path)
    second.close()


def test_ops_manage_xau_microbar_worker() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    start_source = (repo_root / "ops" / "start_trading.sh").read_text(
        encoding="utf-8"
    )
    stop_source = (repo_root / "ops" / "stop_trading.sh").read_text(
        encoding="utf-8"
    )

    assert "xau-microbar-worker.pid" in start_source
    assert "-m app.xau_microbar_worker" in start_source
    assert "Refusing to start a second XAU microbar worker" in start_source
    assert "stop_pid xau-microbar-worker" in stop_source
    assert "app.xau_microbar_worker" in stop_source
