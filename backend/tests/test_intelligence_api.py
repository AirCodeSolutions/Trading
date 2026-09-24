import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.daily_report import DailyTradingReport
from app.domain.execution_audit import ExecutionQualitySummary
from app.domain.portfolio import PortfolioAction, ProspectiveQualificationState
from app.domain.precursor_forward_research import (
    PrecursorForwardResearchReport,
    PrecursorForwardSummary,
)
from app.domain.qualification_history import QualificationHistoryEvent
from app.domain.trading_intelligence import TradingIntelligenceOverview
from app.main import app
from app.services.daily_report import write_daily_trading_report
from app.services.trading_intelligence import (
    INTELLIGENCE_FILE,
    write_trading_intelligence,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=TZ)


def empty_intelligence() -> TradingIntelligenceOverview:
    return TradingIntelligenceOverview(
        generated_at=NOW,
        window_hours=24,
        window_start=NOW.replace(hour=0),
        window_end=NOW,
        market_move_threshold_atr=1.5,
        market_move_horizon_bars=12,
        trades=[],
        opportunities=[],
        assets=[],
        limitations=["test"],
    )


def empty_report() -> DailyTradingReport:
    return DailyTradingReport(
        report_date=NOW.date(),
        generated_at=NOW,
        reference_capital_eur=400,
        execution_mode="paper",
        live_trading_enabled=False,
        broker_is_demo=True,
        portfolio_action=PortfolioAction.NO_TRADE,
        portfolio_reason="waiting",
        paper_closed_pnl_eur_today=0,
        paper_closed_r_today=0,
        paper_open_positions=0,
        paper_open_risk_eur=0,
        bridge_open_positions=0,
        bridge_unrealized_pnl_eur=0,
        broker_realized_pnl_eur_today=None,
        market_opportunities_24h=0,
        captured_opportunities_24h=0,
        missed_opportunities_24h=0,
        qualification_counts={ProspectiveQualificationState.COLLECTING: 1},
        execution_quality=ExecutionQualitySummary(
            commands=0,
            fills=0,
            refused=0,
            errors=0,
            unpaired_results=0,
            average_adverse_slippage_price=0,
            max_adverse_slippage_price=0,
            average_slippage_r=0,
            samples=[],
        ),
        assets=[],
        limitations=["test"],
    )


def test_cached_intelligence_and_daily_report_endpoints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    write_trading_intelligence(tmp_path / INTELLIGENCE_FILE, empty_intelligence())
    write_daily_trading_report(tmp_path, empty_report())

    client = TestClient(app)
    intelligence = client.get("/api/v1/intelligence/overview?hours=24")
    report = client.get("/api/v1/reports/daily")

    assert intelligence.status_code == 200
    assert intelligence.json()["window_hours"] == 24
    assert report.status_code == 200
    assert report.json()["reference_capital_eur"] == 400


def test_qualification_history_endpoint_reads_latest_first(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    path = tmp_path / "qualification_history.jsonl"
    rows = [
        QualificationHistoryEvent(
            at=NOW,
            strategy_id="GBPUSD:directional_pullback_resumption",
            state=ProspectiveQualificationState.COLLECTING,
            closed_trades=1,
            expectancy_r=0.2,
            profit_factor=1.2,
            max_drawdown_r=0.5,
            reason="collecting",
        ),
        QualificationHistoryEvent(
            at=NOW.replace(minute=5),
            strategy_id="GBPUSD:directional_pullback_resumption",
            state=ProspectiveQualificationState.COLLECTING,
            closed_trades=2,
            expectancy_r=0.3,
            profit_factor=1.3,
            max_drawdown_r=0.5,
            reason="collecting",
        ),
    ]
    path.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )

    response = TestClient(app).get("/api/v1/qualification/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert [row["closed_trades"] for row in payload] == [2, 1]


def test_execution_quality_endpoint_is_empty_without_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)

    response = TestClient(app).get("/api/v1/execution/demo/quality")

    assert response.status_code == 200
    assert response.json()["commands"] == 0


def test_legacy_intelligence_cache_loads_with_causal_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    payload = {
        "generated_at": NOW.isoformat(),
        "window_hours": 24,
        "window_start": NOW.replace(hour=0).isoformat(),
        "window_end": NOW.isoformat(),
        "market_move_threshold_atr": 1.5,
        "market_move_horizon_bars": 12,
        "trades": [],
        "opportunities": [
            {
                "episode_id": "legacy-one",
                "symbol": "BTCUSD",
                "side": "buy",
                "birth_at": NOW.isoformat(),
                "horizon_end_at": NOW.replace(hour=13).isoformat(),
                "reference_price": 65000,
                "atr_m5": 100,
                "move_atr": 2.0,
                "capture_state": "missed",
                "matching_strategies": [],
            }
        ],
        "assets": [],
        "limitations": ["legacy"],
    }
    (tmp_path / INTELLIGENCE_FILE).write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    response = TestClient(app).get("/api/v1/intelligence/overview?hours=24")

    assert response.status_code == 200
    body = response.json()
    assert body["causal_patterns"] == []
    assert (
        body["opportunities"][0]["causal_context"]["pattern"]
        == "unclassified"
    )


def test_economic_feasibility_endpoint_reads_cached_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.domain.economic_feasibility import EconomicFeasibilityReport
    from app.services.economic_feasibility import (
        ECONOMIC_FEASIBILITY_FILE,
        write_economic_feasibility_report,
    )

    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    report = EconomicFeasibilityReport(
        generated_at=NOW,
        reference_capital_eur=400,
        risk_fraction=0.01,
        max_spread_to_stop=0.15,
        max_margin_fraction=0.25,
        stop_atr_multiples=[0.5, 0.75, 1.0, 1.5],
        assets=[],
    )
    write_economic_feasibility_report(
        tmp_path / ECONOMIC_FEASIBILITY_FILE,
        report,
    )

    response = TestClient(app).get(
        "/api/v1/research/economic-feasibility"
    )

    assert response.status_code == 200
    assert response.json()["reference_capital_eur"] == 400


def test_economic_feasibility_endpoint_is_404_without_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)

    response = TestClient(app).get(
        "/api/v1/research/economic-feasibility"
    )

    assert response.status_code == 404


def test_precursor_forward_endpoint_is_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    monkeypatch.setattr(settings, "mt4_files_dir", tmp_path)
    report = PrecursorForwardResearchReport(
        generated_at=NOW,
        prospective_started_at=NOW,
        horizon_bars=12,
        raw_resolved=8,
        independent_resolved=3,
        pending=1,
        overall=PrecursorForwardSummary(
            label="all",
            raw_resolved=8,
            independent_resolved=3,
            average_favorable_mfe_atr=2.0,
            average_adverse_mae_atr=1.0,
            average_signed_close_return_atr=0.5,
            favorable_dominance_rate=2 / 3,
            close_alignment_rate=2 / 3,
        ),
        by_pattern=[],
        by_symbol=[],
        recent_independent=[],
    )
    monkeypatch.setattr(
        "app.main.build_precursor_forward_research",
        lambda *args, **kwargs: report,
    )

    response = TestClient(app).get("/api/v1/research/precursor-forward")

    assert response.status_code == 200
    assert response.json()["independent_resolved"] == 3
    assert response.json()["overall"]["average_signed_close_return_atr"] == 0.5


def test_xau_feasible_pullback_endpoint_is_empty_without_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)

    response = TestClient(app).get(
        "/api/v1/research/xau-feasible-pullback"
    )

    assert response.status_code == 200
    assert response.json()["strategy_id"].startswith("XAUUSD:")
    assert response.json()["resolved"] == 0
    assert response.json()["filled"] == 0
