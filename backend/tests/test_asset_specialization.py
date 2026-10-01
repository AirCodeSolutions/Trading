from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.domain.admission import AdmissionState
from app.domain.asset_specialization import (
    ACTIVE_ASSETS,
    AssetMechanismRole,
    AssetSpecializationResearchRequest,
    AssetSpecializationResearchRow,
    EvidenceAlignment,
)
from app.domain.opportunity import OpportunityMechanism, ResearchSplit
from app.main import app
from app.services.asset_specialization import (
    _INCOMPATIBLE,
    _PRIMARY,
    _SECONDARY,
    _alignment,
    build_asset_specialization_snapshots,
    evaluate_asset_specialization,
)

NOW = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Europe/Paris"))


def test_registry_contains_exactly_five_active_assets():
    snapshots = build_asset_specialization_snapshots(Path("/tmp/empty-asset-playbook"), NOW)
    assert [snapshot.symbol for snapshot in snapshots] == list(ACTIVE_ASSETS)
    assert len(snapshots) == 5


def test_profiles_match_registered_hypotheses():
    snapshots = build_asset_specialization_snapshots(Path("/tmp/empty-asset-playbook"), NOW)
    by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}
    for symbol in ACTIVE_ASSETS:
        assert by_symbol[symbol].primary_mechanisms == list(_PRIMARY[symbol])
        assert by_symbol[symbol].secondary_mechanisms == list(_SECONDARY[symbol])
        assert all(row.role is not AssetMechanismRole.PRIMARY_HYPOTHESIS or row.mechanism in _PRIMARY[symbol] for row in by_symbol[symbol].mechanism_evidence)


def test_xag_is_explicitly_viability_research_without_primary_hypothesis():
    snapshot = build_asset_specialization_snapshots(Path("/tmp/empty-asset-playbook"), NOW)[-1]
    assert snapshot.symbol == "XAGUSD"
    assert snapshot.primary_mechanisms == []
    assert snapshot.secondary_mechanisms
    assert snapshot.profile_status.value == "viability_research"


def test_structural_compatibility_is_descriptive_only():
    snapshots = build_asset_specialization_snapshots(Path("/tmp/empty-asset-playbook"), NOW)
    rows = {(snapshot.symbol, row.mechanism): row for snapshot in snapshots for row in snapshot.mechanism_evidence}
    assert rows[("BTCUSD", OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE)].compatible
    assert rows[("XAUUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE)].compatible
    for pair in _INCOMPATIBLE:
        assert rows[pair].compatible is False
        assert rows[pair].evidence_alignment is EvidenceAlignment.NO_EVIDENCE


def test_missing_evidence_does_not_become_economic_zero():
    snapshots = build_asset_specialization_snapshots(Path("/tmp/empty-asset-playbook"), NOW)
    row = snapshots[0].mechanism_evidence[0]
    assert row.evidence_alignment is EvidenceAlignment.NO_EVIDENCE
    assert row.paper_n == 0
    assert row.paper_expectancy_r is None
    assert row.paper_profit_factor is None


def test_removed_or_unknown_symbols_are_rejected_before_research():
    split = ResearchSplit(train_end=NOW - timedelta(days=2), validation_end=NOW - timedelta(days=1))
    for symbol in ("US500Cash", "UNKNOWN"):
        try:
            evaluate_asset_specialization(Path("/tmp/unused"), AssetSpecializationResearchRequest(split=split, symbols=[symbol]))
        except ValueError as exc:
            assert symbol.upper() in str(exc)
        else:
            raise AssertionError("invalid symbol was accepted")


def test_evidence_alignment_covers_conflicts_and_prospective_only():
    assert _alignment(AdmissionState.REJECTED, "supports_demo", True, 20) is EvidenceAlignment.CONFLICTED
    assert _alignment(AdmissionState.ACTIVE, "failed", True, 20) is EvidenceAlignment.CONFLICTED
    assert _alignment(AdmissionState.ACTIVE, "collecting", False, 0) is EvidenceAlignment.HISTORICAL_ONLY
    assert _alignment(None, "supports_demo", True, 20) is EvidenceAlignment.PROSPECTIVE_ONLY
    assert _alignment(None, "failed", True, 20) is EvidenceAlignment.PROSPECTIVE_ONLY
    assert _alignment(None, "collecting", True, 0) is EvidenceAlignment.PROSPECTIVE_COLLECTING


def test_research_row_preserves_average_execution_cost():
    row = AssetSpecializationResearchRow(
        symbol="BTCUSD", mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        role=AssetMechanismRole.PRIMARY_HYPOTHESIS, candidates=4, executed=3, rejected=1,
        rejection_reasons={}, validation_trades=2, validation_expectancy_r=0.2,
        validation_profit_factor=1.4, validation_max_drawdown_r=1.0,
        validation_average_execution_cost_r=0.125, holdout_trades=2,
        holdout_expectancy_r=0.1, holdout_profit_factor=1.2,
        holdout_max_drawdown_r=1.1, holdout_average_execution_cost_r=0.25,
        admission_state=AdmissionState.SHADOW,
    )
    assert row.validation_average_execution_cost_r == 0.125
    assert row.holdout_average_execution_cost_r == 0.25


def test_asset_specialization_get_endpoint_has_five_profiles_and_no_authority():
    response = TestClient(app).get("/api/v1/asset-specialization/v2")
    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload] == list(ACTIVE_ASSETS)
    assert payload[-1]["profile_status"] == "viability_research"
    serialized = str(payload).lower()
    assert all(token not in serialized for token in ("order", "command", "proposal", "approval", "execution"))
