from pathlib import Path

import pytest

from app.core.config import settings
from app.domain.opportunity import PortfolioResearchResult
from app.domain.runtime_capital import RuntimeCapitalSnapshot, RuntimeCapitalSource
from app.domain.strategy_universe import ACTIVE_ASSETS
from app.services.probe_review import default_probe_review_split
from app.services.runtime_admission_refresh import refresh_runtime_admissions


def empty_result() -> PortfolioResearchResult:
    return PortfolioResearchResult(
        results=[],
        skipped_symbols={},
        qualified_strategy_id=None,
        selection_reason="test",
    )


def test_refresh_runtime_admissions_forces_demo_capital_and_frozen_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    captured = {}

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.resolve_demo_sizing_capital",
        lambda path: RuntimeCapitalSnapshot(
            capital_eur=866312.61,
            source=RuntimeCapitalSource.BROKER_EQUITY,
            is_demo=True,
        ),
    )

    def fake_research(files, request, **kwargs):
        captured["files"] = files
        captured["request"] = request
        captured["kwargs"] = kwargs
        return empty_result()

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        fake_research,
    )

    def fake_save(path, result):
        captured["save_path"] = path
        captured["saved"] = result

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.save_research_admissions",
        fake_save,
    )

    result = refresh_runtime_admissions(files_dir, runtime_dir)

    assert result == empty_result()
    request = captured["request"]
    assert request.capital_eur == 866312.61
    assert request.requested_risk_fraction == settings.risk_per_trade_fraction
    assert tuple(request.symbols or ()) == ACTIVE_ASSETS
    assert request.split == default_probe_review_split()
    assert captured["save_path"] == runtime_dir / "strategy_admissions.json"
    assert captured["saved"] == result


def test_refresh_runtime_admissions_fails_closed_without_demo_capital(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.resolve_demo_sizing_capital",
        lambda path: RuntimeCapitalSnapshot(
            source=RuntimeCapitalSource.UNAVAILABLE,
            is_demo=True,
        ),
    )

    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("research must not run")

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        forbidden,
    )

    with pytest.raises(ValueError, match="requires available MT4 DEMO"):
        refresh_runtime_admissions(tmp_path, tmp_path)

    assert called is False
