from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.services.authority_recovery import (
    HYPOTHESIS_ID,
    MIN_OBSERVATIONS,
    build_authority_recovery_report,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 10, 1, 17, 30, tzinfo=TZ)


def trade(i: int, result_r: float, mechanism: OpportunityMechanism) -> ShadowPaperTrade:
    signal = NOW - timedelta(hours=2, minutes=i)
    return ShadowPaperTrade(
        trade_id=f"probe-{i}", symbol="XAUUSD", mechanism=mechanism, side=Side.BUY,
        signal_at=signal, entry_bar_at=signal, opened_at=signal,
        entry_price=100.0, stop_price=99.0, target_price=101.5,
        spread_at_entry=0.1, lots=1.0, risk_eur=100.0, risk_distance=1.0,
        target_r=1.5, max_holding_bars=12,
        status=PaperTradeStatus.TARGET if result_r > 0 else PaperTradeStatus.STOP,
        exit_at=signal + timedelta(minutes=10), exit_price=101.5 if result_r > 0 else 99.0,
        result_r=result_r, pnl_eur=result_r * 100.0, bars_held=2,
    )


def test_contract_uses_existing_twenty_observation_governance() -> None:
    assert HYPOTHESIS_ID == "recover_rejected_xau_structural_displacement_1_5r_v1"
    assert MIN_OBSERVATIONS == 20


def test_n_below_twenty_is_insufficient_and_never_changes_authority(tmp_path: Path, monkeypatch) -> None:
    import app.services.authority_recovery as service

    rows = [
        trade(1, 1.5, OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE),
        trade(2, -1.0, OpportunityMechanism.FAILED_AUCTION_REVERSAL),
    ]
    monkeypatch.setattr(service, "_resolved_unqualified_rows", lambda _: rows)

    report = build_authority_recovery_report(tmp_path, now=NOW, window_hours=168)

    assert report.candidate_resolved == 1
    assert report.candidate_total_r == 1.5
    assert report.evidence_state == "insufficient_evidence"
    assert report.required_additional_observations == 19
    assert report.authority_effect is False
    assert report.human_review_required is True
    assert report.supports_demo is False
