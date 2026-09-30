from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domain.champion_challengers import ChallengerEvidenceState, EconomicChangeAxis
from app.domain.opportunity import OpportunityMechanism
from app.domain.position_manager import PositionManagerComparison, PositionManagerReport
from app.services.asset_specialization import build_asset_specialization_snapshots
from app.services.champion_challengers import build_champion_challenger_report

NOW = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Europe/Paris"))


def pm_rows(count: int, delta: float = 0.3) -> list[PositionManagerComparison]:
    return [PositionManagerComparison(
        trade_id=str(index), symbol="XAUUSD", mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        baseline_result_r=0.5, v2_result_r=0.5 + delta / count, delta_r=delta / count,
        baseline_mfe_capture=0.4, v2_mfe_capture=0.6, baseline_giveback_r=0.3, v2_giveback_r=0.1,
    ) for index in range(count)]


def report(rows):
    return PositionManagerReport(generated_at=NOW, window_hours=168, trades=len(rows), pending=0, comparisons=rows)


def test_one_baseline_and_three_single_axis_challengers_per_family():
    result = build_champion_challenger_report(build_asset_specialization_snapshots(Path("/tmp/empty"), NOW))
    assert result.family_count == 33
    assert all(family.champion.variant_id == "BASELINE_V1" for family in result.families)
    assert all(len(family.challengers) == 3 for family in result.families)
    assert all(len({challenger.economic_axis for challenger in family.challengers}) == 3 for family in result.families)
    assert all(challenger.auto_promote is False for family in result.families for challenger in family.challengers)


def test_position_manager_pairs_aggregate_and_become_reviewable_at_twenty():
    assets = build_asset_specialization_snapshots(Path("/tmp/empty"), NOW)
    rows = pm_rows(20)
    result = build_champion_challenger_report(assets, report(rows))
    family = next(item for item in result.families if item.family_id == "XAUUSD:failed_auction_reversal")
    pm = next(item for item in family.challengers if item.variant_id == "POSITION_MANAGER_V2")
    assert pm.paired_n == 20
    assert pm.delta_total_r == pytest.approx(0.3)
    assert pm.evidence_state is ChallengerEvidenceState.REVIEWABLE
    assert pm.economic_axis is EconomicChangeAxis.EXIT_MANAGEMENT


def test_pending_invalid_and_missing_delta_are_excluded():
    rows = pm_rows(2)
    rows[0].pending = True
    rows[1].invalid_data = True
    rows.extend([pm_rows(1, 0.5)[0].model_copy(update={"delta_r": None})])
    assets = build_asset_specialization_snapshots(Path("/tmp/empty"), NOW)
    result = build_champion_challenger_report(assets, report(rows))
    family = next(item for item in result.families if item.family_id == "XAUUSD:failed_auction_reversal")
    pm = next(item for item in family.challengers if item.variant_id == "POSITION_MANAGER_V2")
    assert pm.paired_n == 0
    assert pm.evidence_state is ChallengerEvidenceState.NO_EVIDENCE


def test_trigger_and_entry_zone_never_reviewable_without_paired_outcomes():
    assets = build_asset_specialization_snapshots(Path("/tmp/empty"), NOW)
    result = build_champion_challenger_report(assets)
    for family in result.families:
        assert all(challenger.evidence_state is ChallengerEvidenceState.NO_EVIDENCE for challenger in family.challengers if challenger.variant_id != "POSITION_MANAGER_V2")
        assert all(challenger.evidence.human_review_required for challenger in family.challengers)
