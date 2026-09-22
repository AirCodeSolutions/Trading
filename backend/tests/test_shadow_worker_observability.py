from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.portfolio import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    TradingOverview,
)
from app.shadow_worker import _update_observability

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=TZ)


def overview() -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=None,
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=400,
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=0,
            research_paper_open_positions=0,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=12,
            remaining_daily_loss_budget_eur=12,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.NO_TRADE,
            selected_strategy_id=None,
            reason="waiting",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[],
        paper_strategies=[],
    )


def test_observability_failures_are_returned_without_raising(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    monkeypatch.setattr(
        "app.shadow_worker.read_demo_result",
        lambda path: None,
    )
    monkeypatch.setattr(
        "app.shadow_worker.append_bridge_result_if_new",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("audit down")),
    )
    monkeypatch.setattr(
        "app.shadow_worker.record_qualification_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("history down")),
    )
    monkeypatch.setattr(
        "app.shadow_worker._snapshot_due",
        lambda path: True,
    )
    monkeypatch.setattr(
        "app.shadow_worker.build_trading_intelligence",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("intel down")),
    )

    errors = _update_observability(
        audit_path=tmp_path / "audit.jsonl",
        qualification_path=tmp_path / "qualification.jsonl",
        intelligence_path=tmp_path / "intelligence.json",
        overview=overview(),
        now=NOW,
    )

    assert len(errors) == 3
    assert errors[0].startswith("execution_audit:")
    assert errors[1].startswith("qualification_history:")
    assert errors[2].startswith("intelligence_snapshot:")
