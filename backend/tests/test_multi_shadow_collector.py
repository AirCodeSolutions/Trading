from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity import OpportunityMechanism
from app.services.multi_shadow_collector import (
    paper_entry_allowed,
    shadow_mechanism_enabled,
)


def decision(state: AdmissionState) -> AdmissionDecision:
    return AdmissionDecision(
        strategy_id="EURUSD:test",
        state=state,
        reason="test",
        weakest_expectancy_r=0.1,
        worst_drawdown_r=1.0,
    )


def test_missing_admission_cannot_open_new_paper_trade() -> None:
    assert paper_entry_allowed(None) is False


def test_rejected_admission_cannot_open_new_paper_trade() -> None:
    assert paper_entry_allowed(decision(AdmissionState.REJECTED)) is False


def test_shadow_admission_can_open_new_paper_trade() -> None:
    assert paper_entry_allowed(decision(AdmissionState.SHADOW)) is True



def test_directional_pullback_shadow_is_limited_to_gbpusd() -> None:
    mechanism = OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION

    assert shadow_mechanism_enabled("GBPUSD", mechanism) is True
    assert shadow_mechanism_enabled("EURUSD", mechanism) is False
    assert shadow_mechanism_enabled("BTCUSD", mechanism) is False


def test_existing_mechanisms_remain_enabled_for_all_watched_symbols() -> None:
    assert shadow_mechanism_enabled(
        "EURUSD",
        OpportunityMechanism.FAILED_AUCTION_REVERSAL,
    ) is True
