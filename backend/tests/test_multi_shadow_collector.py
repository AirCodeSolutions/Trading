from app.domain.admission import AdmissionDecision, AdmissionState
from app.services.multi_shadow_collector import paper_entry_allowed


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
