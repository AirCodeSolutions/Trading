from datetime import UTC

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_is_safe_by_default() -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "paper"
    assert payload["decision_mode"] == "confirm"
    assert payload["live_trading_enabled"] is False
    assert payload["demo_collection_enabled"] is False
    assert payload["demo_execution_bridge_enabled"] is False
    assert payload["allowed_timeframes"] == ["M5", "M15"]
    assert payload["reference_capital_eur"] == 400.0
    assert payload["risk_per_trade_fraction"] == 0.01
    assert payload["max_lots_per_trade"] == 5.0
    assert payload["absolute_max_risk_fraction"] == 0.02
    assert payload["prospective_min_trades"] == 20
    assert payload["historical_validation_min_trades"] == 40
    assert payload["historical_holdout_min_trades"] == 20


def test_ingest_and_read_m5_bar() -> None:
    bar = {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "timestamp": "2026-09-18T12:00:00Z",
        "open": 3600.0,
        "high": 3605.0,
        "low": 3598.0,
        "close": 3602.0,
        "volume": 100.0,
    }
    response = client.post("/api/v1/market/bars", json=bar)
    assert response.status_code == 201

    latest = client.get("/api/v1/market/XAUUSD/M5/latest")
    assert latest.status_code == 200
    assert latest.json()["close"] == 3602.0


def test_paired_economic_contracts_endpoint_is_research_only() -> None:
    response = client.get(
        "/api/v1/research/paired-economic-contracts/xau-structural-displacement"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["family_id"] == "XAUUSD:structural_displacement_sequence"
    assert payload["broker_authority"] is False
    assert payload["human_review_required"] is True
    assert payload["champion"]["contract_id"] == "xau_sd_target_1r_v1"
    assert payload["challenger"]["contract_id"] == "xau_sd_target_1_5r_v2"


def test_authority_regret_endpoint_is_descriptive() -> None:
    response = client.get("/api/v1/research/authority-regret?hours=24")
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 24
    assert "winners_missed" in payload
    assert "losses_avoided" in payload
    assert "guard_blocked_total_r" in payload
    assert "cost_basis" in payload


def test_authority_regret_endpoint_rejects_invalid_window() -> None:
    response = client.get("/api/v1/research/authority-regret?hours=0")
    assert response.status_code == 422


def _runtime_admission_report():
    from datetime import datetime

    from app.domain.runtime_admission_refresh import RuntimeAdmissionRefreshReport

    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    return RuntimeAdmissionRefreshReport(
        generated_at=now,
        applied=False,
        apply_allowed=True,
        capital_eur=866312.61,
        capital_source="broker_equity",
        active_assets=["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"],
        train_end=now,
        validation_end=now,
        evaluated_results=33,
        drain_enabled=True,
        book_flat=True,
        paper_open_positions=0,
        bridge_open_positions=0,
        pending_open_command=False,
        pending_close_command=False,
        added=1,
        removed=0,
        changed=2,
        unchanged=30,
        registry_path="/tmp/strategy_admissions.json",
        receipt_path="/tmp/runtime_admission_refresh_receipt.json",
    )


def test_runtime_admission_preview_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "app.main.preview_runtime_admissions",
        lambda *args, **kwargs: _runtime_admission_report(),
    )
    response = client.post("/api/v1/research/runtime-admissions/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is False
    assert payload["apply_allowed"] is True
    assert payload["changed"] == 2


def test_runtime_admission_refresh_endpoint_returns_controlled_report(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)
    report = _runtime_admission_report().model_copy(update={"applied": True})
    monkeypatch.setattr(
        "app.main.refresh_runtime_admissions",
        lambda *args, **kwargs: report,
    )
    response = client.post("/api/v1/research/runtime-admissions/refresh")
    assert response.status_code == 200
    assert response.json()["applied"] is True


def test_runtime_admission_refresh_endpoint_returns_409_when_guard_blocks(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    def blocked(*args, **kwargs):
        raise ValueError("runtime admission refresh apply blocked: runtime drain must be ON")

    monkeypatch.setattr("app.main.refresh_runtime_admissions", blocked)
    response = client.post("/api/v1/research/runtime-admissions/refresh")
    assert response.status_code == 409
    assert "drain must be ON" in response.json()["detail"]


def test_regime_session_attribution_endpoint_is_descriptive(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    from datetime import UTC, datetime

    from app.domain.regime import MarketRegime
    from app.domain.regime_session_attribution import RegimeSessionAttributionReport

    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    report = RegimeSessionAttributionReport(
        generated_at=now,
        symbol="XAUUSD",
        strategy_id="XAUUSD:structural_displacement_sequence",
        target_r=1.5,
        capital_eur=866312.61,
        capital_source="broker_equity",
        train_end=now,
        validation_end=now,
        validation_trades=25,
        holdout_trades=14,
        session_buckets=[],
        regime_buckets=[],
        session_partition=["asia", "london", "us", "transition"],
        regime_partition=list(MarketRegime),
        authority_effect=False,
    )
    monkeypatch.setattr(
        "app.main.build_xau_structural_displacement_regime_session_attribution",
        lambda *args, **kwargs: report,
    )

    response = client.get(
        "/api/v1/research/xau-structural-displacement/regime-session-attribution"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "XAUUSD:structural_displacement_sequence"
    assert payload["target_r"] == 1.5
    assert payload["validation_trades"] == 25
    assert payload["holdout_trades"] == 14
    assert payload["authority_effect"] is False
    assert payload["session_partition"] == ["asia", "london", "us", "transition"]


def test_execution_cost_stress_endpoint_is_descriptive(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    from datetime import UTC, datetime

    from app.domain.execution_cost_stress import (
        CostStressScenario,
        CostStressScenarioResult,
        CostStressWindowMetrics,
        ExecutionCostStressReport,
    )

    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    metrics = CostStressWindowMetrics(
        trades=10,
        total_r=4.0,
        expectancy_r=0.4,
        profit_factor=2.0,
        max_drawdown_r=2.0,
        average_execution_cost_r=0.06,
    )
    report = ExecutionCostStressReport(
        generated_at=now,
        symbol="XAUUSD",
        strategy_id="XAUUSD:structural_displacement_sequence",
        target_r=1.5,
        capital_eur=866312.61,
        capital_source="broker_equity",
        baseline_spread=0.2,
        scenarios=[
            CostStressScenarioResult(
                scenario=CostStressScenario.OBSERVED,
                spread_multiplier=1.0,
                slippage_spread_fraction=0.25,
                effective_spread=0.2,
                validation=metrics,
                holdout=metrics,
                weakest_expectancy_r=0.4,
                weakest_profit_factor=2.0,
                worst_drawdown_r=2.0,
                positive_both_windows=True,
                authority_effect=False,
            )
        ],
        all_scenarios_positive_both_windows=True,
        authority_effect=False,
    )
    monkeypatch.setattr(
        "app.main.build_xau_structural_displacement_cost_stress",
        lambda *args, **kwargs: report,
    )

    response = client.get(
        "/api/v1/research/xau-structural-displacement/execution-cost-stress"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "XAUUSD:structural_displacement_sequence"
    assert payload["target_r"] == 1.5
    assert payload["all_scenarios_positive_both_windows"] is True
    assert payload["authority_effect"] is False

def test_family_exit_challenger_endpoint_is_research_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    from datetime import UTC, datetime

    from app.domain.family_exit_challenger import (
        ExitChallengerWindowMetrics,
        FamilyExitChallengerReport,
    )

    metrics = ExitChallengerWindowMetrics(
        paired_trades=10,
        champion_total_r=4.0,
        challenger_total_r=3.5,
        delta_total_r=-0.5,
        champion_expectancy_r=0.4,
        challenger_expectancy_r=0.35,
        champion_profit_factor=2.0,
        challenger_profit_factor=1.8,
        champion_max_drawdown_r=2.0,
        challenger_max_drawdown_r=2.0,
        champion_targets=4,
        challenger_targets=3,
        champion_stops=3,
        challenger_stops=3,
        champion_timeouts=3,
        challenger_timeouts=4,
    )
    report = FamilyExitChallengerReport(
        generated_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        symbol="XAUUSD",
        strategy_id="XAUUSD:structural_displacement_sequence",
        hypothesis_id="xau_sd_fixed_target_1_5r_vs_2r_exit_v1",
        change_axis="fixed_target_r",
        champion_target_r=1.5,
        challenger_target_r=2.0,
        max_holding_bars=12,
        capital_eur=866314.66,
        capital_source="broker_equity",
        validation=metrics,
        holdout=metrics,
        authority_effect=False,
        human_review_required=True,
    )
    monkeypatch.setattr(
        "app.main.build_xau_structural_displacement_exit_challenger",
        lambda *args, **kwargs: report,
    )

    response = client.get(
        "/api/v1/research/xau-structural-displacement/family-exit-challenger"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["champion_target_r"] == 1.5
    assert payload["challenger_target_r"] == 2.0
    assert payload["validation"]["delta_total_r"] == -0.5
    assert payload["authority_effect"] is False
    assert payload["human_review_required"] is True

def test_conditional_exit_challenger_endpoint_is_research_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    from datetime import UTC, datetime

    from app.domain.family_exit_challenger import (
        ExitChallengerWindowMetrics,
        FamilyExitChallengerReport,
    )

    metrics = ExitChallengerWindowMetrics(
        paired_trades=10,
        champion_total_r=4.0,
        challenger_total_r=3.0,
        delta_total_r=-1.0,
        champion_expectancy_r=0.4,
        challenger_expectancy_r=0.3,
        champion_profit_factor=2.0,
        challenger_profit_factor=1.7,
        champion_max_drawdown_r=2.0,
        challenger_max_drawdown_r=2.0,
        champion_targets=4,
        challenger_targets=3,
        champion_stops=3,
        challenger_stops=3,
        champion_timeouts=3,
        challenger_timeouts=4,
        extension_qualified=2,
    )
    report = FamilyExitChallengerReport(
        generated_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        symbol="XAUUSD",
        strategy_id="XAUUSD:structural_displacement_sequence",
        hypothesis_id="xau_sd_extend_2r_if_prior_3_m5_directional_v1",
        change_axis="conditional_target_extension",
        champion_target_r=1.5,
        challenger_target_r=2.0,
        max_holding_bars=12,
        capital_eur=866318.79,
        capital_source="broker_equity",
        validation=metrics,
        holdout=metrics,
        authority_effect=False,
        human_review_required=True,
        qualification_rule="three prior directional closes",
    )
    monkeypatch.setattr(
        "app.main.build_xau_structural_displacement_conditional_extension",
        lambda *args, **kwargs: report,
    )

    response = client.get(
        "/api/v1/research/xau-structural-displacement/conditional-exit-challenger"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["hypothesis_id"] == "xau_sd_extend_2r_if_prior_3_m5_directional_v1"
    assert payload["validation"]["extension_qualified"] == 2
    assert payload["authority_effect"] is False
    assert payload["human_review_required"] is True


def test_landmark_exit_challenger_endpoint_is_research_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.main._mt4_files_dir", lambda: tmp_path)

    from datetime import UTC, datetime

    from app.domain.family_exit_challenger import (
        ExitChallengerWindowMetrics,
        FamilyExitChallengerReport,
    )

    metrics = ExitChallengerWindowMetrics(
        paired_trades=14, champion_total_r=9.2, challenger_total_r=7.2,
        delta_total_r=-2.0, champion_expectancy_r=0.65, challenger_expectancy_r=0.51,
        champion_profit_factor=3.3, challenger_profit_factor=2.8,
        champion_max_drawdown_r=2.0, challenger_max_drawdown_r=2.0,
        champion_targets=7, challenger_targets=2, champion_stops=4, challenger_stops=4,
        champion_timeouts=3, challenger_timeouts=8, extension_qualified=11,
    )
    report = FamilyExitChallengerReport(
        generated_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        symbol="XAUUSD", strategy_id="XAUUSD:structural_displacement_sequence",
        hypothesis_id="xau_sd_target_nearest_frozen_landmark_beyond_1_5r_v1",
        change_axis="frozen_landmark_target", champion_target_r=1.5, challenger_target_r=1.5,
        max_holding_bars=12, capital_eur=866318.79, capital_source="broker_equity",
        validation=metrics, holdout=metrics, authority_effect=False, human_review_required=True,
        qualification_rule="nearest frozen side-aligned landmark beyond 1.5R",
    )
    monkeypatch.setattr(
        "app.main.build_xau_structural_displacement_landmark_extension",
        lambda *args, **kwargs: report,
    )
    response = client.get(
        "/api/v1/research/xau-structural-displacement/landmark-exit-challenger"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["holdout"]["extension_qualified"] == 11
    assert payload["authority_effect"] is False
    assert payload["human_review_required"] is True


def test_authority_recovery_endpoint_is_descriptive(monkeypatch) -> None:
    from datetime import UTC, datetime

    from app.domain.authority_recovery import AuthorityRecoveryReport

    report = AuthorityRecoveryReport(
        generated_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        window_hours=168, hypothesis_id="recover_rejected_xau_structural_displacement_1_5r_v1",
        strategy_id="XAUUSD:structural_displacement_sequence", candidate_resolved=1,
        wins=0, losses=1, flats=0, candidate_total_r=-1.0, expectancy_r=-1.0,
        profit_factor=0.0, max_drawdown_r=1.0, minimum_observations=20,
        required_additional_observations=19, evidence_state="insufficient_evidence",
        supports_demo=False, authority_effect=False, human_review_required=True,
    )
    monkeypatch.setattr("app.main.build_authority_recovery_report", lambda *args, **kwargs: report)
    response = client.get("/api/v1/research/authority-recovery?hours=168")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_state"] == "insufficient_evidence"
    assert payload["required_additional_observations"] == 19
    assert payload["supports_demo"] is False
    assert payload["authority_effect"] is False
