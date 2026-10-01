from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.opportunity import OpportunityMechanism
from app.domain.strategy_universe import (
    ACTIVE_ASSETS,
    INCOMPATIBLE_FAMILIES,
    MECHANISM_SLUGS,
    compatible_mechanisms,
    mechanism_is_compatible,
    strategy_id,
)
from app.services.position_manager_runtime import build_runtime_position_manager_report

NOW = datetime(2026, 10, 1, 8, tzinfo=ZoneInfo("Europe/Athens"))


def test_runtime_and_research_share_one_active_asset_universe():
    assert settings.session_watch_symbols == ACTIVE_ASSETS
    assert ACTIVE_ASSETS == ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD")


def test_compatibility_contract_has_exactly_33_families():
    compatible = [
        (symbol, mechanism)
        for symbol in ACTIVE_ASSETS
        for mechanism in OpportunityMechanism
        if mechanism_is_compatible(symbol, mechanism)
    ]
    assert len(compatible) == 33
    assert len(INCOMPATIBLE_FAMILIES) == 7
def test_structural_compatibility_has_one_source_of_truth():
    displacement = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
    persistence = OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE
    assert mechanism_is_compatible("BTCUSD", displacement)
    assert mechanism_is_compatible("XAUUSD", displacement)
    assert not mechanism_is_compatible("EURUSD", displacement)
    assert mechanism_is_compatible("XAUUSD", persistence)
    assert not mechanism_is_compatible("BTCUSD", persistence)
    assert persistence not in compatible_mechanisms("GBPUSD")


def test_slug_and_strategy_id_contracts_are_canonical():
    assert len(MECHANISM_SLUGS) == len(OpportunityMechanism)
    assert MECHANISM_SLUGS["break_retest"] is OpportunityMechanism.BREAK_RETEST_REACCEL
    assert strategy_id("xauusd", OpportunityMechanism.FAILED_AUCTION_REVERSAL) == (
        "XAUUSD:failed_auction_reversal"
    )


def test_runtime_position_manager_loader_is_empty_safe(tmp_path):
    report = build_runtime_position_manager_report(
        tmp_path / "mt4",
        tmp_path / "runtime",
        now=NOW,
        window_hours=168,
    )
    assert report.trades == 0
    assert report.pending == 0
    assert report.comparisons == []
