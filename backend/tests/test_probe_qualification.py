from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_funnel import ResearchProbeQualificationState
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.services.probe_qualification import (
    assess_research_probe_evidence,
    paper_entry_allowed_with_probe_evidence,
    probe_supports_paper,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=TZ)
STRATEGY = "XAUUSD:directional_transition"


def probe(index: int, result_r: float) -> ShadowPaperTrade:
    opened_at = NOW - timedelta(minutes=5 * (20 - index))
    status = PaperTradeStatus.TARGET if result_r > 0 else PaperTradeStatus.STOP
    return ShadowPaperTrade(
        trade_id=f"probe-{index}",
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        side=Side.BUY,
        signal_at=opened_at,
        entry_bar_at=opened_at,
        opened_at=opened_at,
        entry_price=4160.0,
        stop_price=4156.0,
        target_price=4166.0,
        spread_at_entry=0.28,
        lots=1.0,
        risk_eur=400.0,
        risk_distance=4.0,
        target_r=1.5,
        max_holding_bars=12,
        status=status,
        exit_at=opened_at + timedelta(minutes=5),
        exit_price=4166.0 if result_r > 0 else 4156.0,
        result_r=result_r,
        pnl_eur=400.0 * result_r,
        bars_held=1,
    )


def admission(state: AdmissionState) -> AdmissionDecision:
    return AdmissionDecision(
        strategy_id=STRATEGY,
        state=state,
        reason="test",
        weakest_expectancy_r=0.0,
        worst_drawdown_r=0.0,
        paper_collection_candidate=False,
    )


def test_probe_evidence_reuses_existing_twenty_trade_gate() -> None:
    qualification = assess_research_probe_evidence(
        STRATEGY,
        [probe(index, 1.0) for index in range(20)],
    )

    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.SUPPORTS_REVIEW
    assert qualification.closed_trades == 20
    assert qualification.expectancy_r == 1.0
    assert qualification.profit_factor == 99.0
    assert qualification.max_drawdown_r == 0.0


def test_probe_evidence_stays_collecting_before_twenty() -> None:
    qualification = assess_research_probe_evidence(
        STRATEGY,
        [probe(index, 1.0) for index in range(19)],
    )

    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.COLLECTING
    assert qualification.closed_trades == 19


def test_probe_promotion_is_shadow_only() -> None:
    qualification = assess_research_probe_evidence(
        STRATEGY,
        [probe(index, 1.0) for index in range(20)],
    )

    assert probe_supports_paper(admission(AdmissionState.SHADOW), qualification)
    assert paper_entry_allowed_with_probe_evidence(
        admission(AdmissionState.SHADOW),
        qualification,
    )
    assert not probe_supports_paper(
        admission(AdmissionState.REJECTED),
        qualification,
    )
    assert not paper_entry_allowed_with_probe_evidence(
        admission(AdmissionState.REJECTED),
        qualification,
    )


def test_failed_probe_evidence_does_not_promote_shadow() -> None:
    qualification = assess_research_probe_evidence(
        STRATEGY,
        [probe(index, -1.0) for index in range(20)],
    )

    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.FAILED
    assert not probe_supports_paper(admission(AdmissionState.SHADOW), qualification)
    assert not paper_entry_allowed_with_probe_evidence(
        admission(AdmissionState.SHADOW),
        qualification,
    )
