from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity import (
    OpportunityBacktestResult,
    OpportunityMechanism,
    PerformanceSummary,
    PortfolioResearchResult,
)
from app.domain.runtime_capital import RuntimeCapitalSnapshot, RuntimeCapitalSource
from app.domain.strategy_universe import ACTIVE_ASSETS
from app.services.probe_review import default_probe_review_split
from app.services.runtime_admission_refresh import (
    preview_runtime_admissions,
    refresh_runtime_admissions,
)

NOW = datetime(2026, 10, 1, 14, 0, tzinfo=ZoneInfo("Europe/Athens"))


def summary() -> PerformanceSummary:
    return PerformanceSummary(
        trades=20,
        total_r=4.0,
        expectancy_r=0.2,
        profit_factor=1.4,
        win_rate=0.55,
        max_drawdown_r=3.0,
        total_pnl_eur=400.0,
        average_execution_cost_r=0.05,
    )


def decision(
    state: AdmissionState,
    *,
    reason: str,
    expectancy: float,
    candidate: bool,
) -> AdmissionDecision:
    return AdmissionDecision(
        strategy_id="XAUUSD:structural_displacement_sequence",
        state=state,
        reason=reason,
        weakest_expectancy_r=expectancy,
        worst_drawdown_r=3.0,
        paper_collection_candidate=candidate,
    )


def result(
    admission: AdmissionDecision,
    *,
    skipped: dict[str, str] | None = None,
) -> PortfolioResearchResult:
    row = OpportunityBacktestResult(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        candidates=20,
        executed=20,
        rejected=0,
        rejection_reasons={},
        train=summary(),
        validation=summary(),
        holdout=summary(),
        admission=admission,
    )
    return PortfolioResearchResult(
        results=[row],
        skipped_symbols=skipped or {},
        qualified_strategy_id=None,
        selection_reason="test",
    )


def demo_capital() -> RuntimeCapitalSnapshot:
    return RuntimeCapitalSnapshot(
        capital_eur=866312.61,
        source=RuntimeCapitalSource.BROKER_EQUITY,
        is_demo=True,
    )


def flat_operational(*, drain: bool = True) -> dict[str, object]:
    return {
        "drain_enabled": drain,
        "paper_open_positions": 0,
        "bridge_open_positions": 0,
        "pending_open_command": False,
        "pending_close_command": False,
        "book_flat": True,
    }


def test_preview_uses_demo_equity_frozen_split_and_does_not_write(
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
        lambda path: demo_capital(),
    )

    after = decision(
        AdmissionState.SHADOW,
        reason="new",
        expectancy=0.2,
        candidate=True,
    )
    before = decision(
        AdmissionState.REJECTED,
        reason="old",
        expectancy=-0.1,
        candidate=False,
    )

    def fake_research(files, request, **kwargs):
        captured["files"] = files
        captured["request"] = request
        captured["kwargs"] = kwargs
        return result(after)

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        fake_research,
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.load_research_admissions",
        lambda path: {before.strategy_id: before},
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh._operational_state",
        lambda *args, **kwargs: flat_operational(drain=False),
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.save_research_admissions",
        lambda *args, **kwargs: pytest.fail("preview must not write registry"),
    )

    report = preview_runtime_admissions(
        files_dir,
        runtime_dir,
        now=NOW,
    )

    request = captured["request"]
    assert request.capital_eur == 866312.61
    assert request.requested_risk_fraction == settings.risk_per_trade_fraction
    assert tuple(request.symbols or ()) == ACTIVE_ASSETS
    assert request.split == default_probe_review_split()
    assert report.applied is False
    assert report.apply_allowed is False
    assert report.apply_blockers == ["runtime drain must be ON"]
    assert report.changed == 1
    assert report.changes[0].before_state == "rejected"
    assert report.changes[0].after_state == "shadow"


def test_apply_requires_guard_then_writes_registry_and_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    after = decision(
        AdmissionState.SHADOW,
        reason="collect",
        expectancy=0.2,
        candidate=True,
    )
    research_result = result(after)
    saved = {}

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.resolve_demo_sizing_capital",
        lambda path: demo_capital(),
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        lambda *args, **kwargs: research_result,
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.load_research_admissions",
        lambda path: {},
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh._operational_state",
        lambda *args, **kwargs: flat_operational(),
    )

    def fake_save(path, payload):
        saved["path"] = path
        saved["payload"] = payload

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.save_research_admissions",
        fake_save,
    )

    report = refresh_runtime_admissions(
        files_dir,
        runtime_dir,
        now=NOW,
    )

    assert report.applied is True
    assert report.apply_allowed is True
    assert report.added == 1
    assert saved["path"] == runtime_dir / "strategy_admissions.json"
    assert saved["payload"] == research_result
    receipt = runtime_dir / "runtime_admission_refresh_receipt.json"
    assert receipt.is_file()
    assert '"applied": true' in receipt.read_text(encoding="utf-8").lower()


def test_apply_fails_closed_when_research_skips_symbol(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.resolve_demo_sizing_capital",
        lambda path: demo_capital(),
    )
    after = decision(
        AdmissionState.SHADOW,
        reason="collect",
        expectancy=0.2,
        candidate=True,
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        lambda *args, **kwargs: result(
            after,
            skipped={"XAGUSD": "history unavailable"},
        ),
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.load_research_admissions",
        lambda path: {},
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh._operational_state",
        lambda *args, **kwargs: flat_operational(),
    )
    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.save_research_admissions",
        lambda *args, **kwargs: pytest.fail("blocked apply must not write"),
    )

    with pytest.raises(ValueError, match="skipped symbols"):
        refresh_runtime_admissions(
            tmp_path,
            tmp_path,
            now=NOW,
        )


def test_preview_fails_closed_without_demo_capital(
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

    monkeypatch.setattr(
        "app.services.runtime_admission_refresh.run_mt4_portfolio_research",
        lambda *args, **kwargs: pytest.fail("research must not run"),
    )

    with pytest.raises(ValueError, match="requires available MT4 DEMO"):
        preview_runtime_admissions(
            tmp_path,
            tmp_path,
            now=NOW,
        )
