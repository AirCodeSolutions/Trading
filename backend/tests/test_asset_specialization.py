from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.asset_specialization import (
    ACTIVE_ASSETS,
    AssetMechanismRole,
    EvidenceAlignment,
)
from app.domain.opportunity import OpportunityMechanism
from app.services.asset_specialization import (
    _INCOMPATIBLE,
    _PRIMARY,
    _SECONDARY,
    build_asset_specialization_snapshots,
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

