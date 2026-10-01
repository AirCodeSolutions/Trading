from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.authority_regret import AuthorityRegretOutcome
from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import (
    ProspectiveQualification,
    ProspectiveQualificationState,
)
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.trading import Side
from app.services.authority_regret import (
    advance_authority_regret_book,
    build_authority_regret_summary,
    load_authority_regret_records,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 10, 1, 12, 0, tzinfo=TZ)
STRATEGY = "XAUUSD:structural_displacement_sequence"
PREFIX = "XAUUSD_structural_displacement_sequence"


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=100.0,
        ask=100.1,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=10.0,
    )
def diagnostic(signal_offset_minutes: int = 0) -> ShadowOpportunityDiagnostic:
    latest = START + timedelta(minutes=signal_offset_minutes)
    return ShadowOpportunityDiagnostic(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        evaluated_at=latest + timedelta(minutes=5, seconds=2),
        latest_closed_m5_at=latest,
        latest_closed_m15_at=latest - timedelta(minutes=15),
        state=ShadowSignalState.SIGNAL_EXECUTABLE,
        side=Side.BUY,
        regime=MarketRegime.DIRECTIONAL,
        regime_direction=1,
        atr_m15=1.5,
        atr_ratio=1.2,
        volatility_percentile=0.7,
        momentum_12_atr=2.0,
        efficiency=0.7,
        structural_stop=99.1,
        target_r=1.0,
        max_holding_bars=12,
        base_risk=ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=True,
            reason="approved",
            lots=5.0,
            expected_loss_eur=5.0,
            spread_to_stop=0.1,
        ),
        max_risk=ShadowSizingSnapshot(
            risk_fraction=0.02,
            approved=True,
            reason="approved",
            lots=5.0,
            expected_loss_eur=10.0,
            spread_to_stop=0.1,
        ),
        reason="test",
    )


def qualification(
    state: ProspectiveQualificationState,
) -> ProspectiveQualification:
    supported = state == ProspectiveQualificationState.SUPPORTS_DEMO
    return ProspectiveQualification(
        strategy_id=STRATEGY,
        state=state,
        closed_trades=20 if supported else 5,
        expectancy_r=0.2 if supported else -0.1,
        profit_factor=1.4 if supported else 0.8,
        max_drawdown_r=3.0 if supported else 5.0,
        reason=state.value,
    )
def admission(state: AdmissionState = AdmissionState.SHADOW) -> AdmissionDecision:
    return AdmissionDecision(
        strategy_id=STRATEGY,
        state=state,
        reason="test",
        weakest_expectancy_r=0.2,
        worst_drawdown_r=3.0,
        paper_collection_candidate=True,
    )


def bar(
    minute: int,
    *,
    high: float,
    low: float = 99.8,
    close: float = 100.5,
) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=minute),
        open=100.1,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def advance(
    tmp_path: Path,
    *,
    diag: ShadowOpportunityDiagnostic,
    qualification_state: ProspectiveQualificationState,
    bars: list[MarketBar],
    effective_paper_entry_allowed: bool = True,
    historical_state: AdmissionState = AdmissionState.SHADOW,
) -> None:
    advance_authority_regret_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=bars,
        runtime_dir=tmp_path,
        prefix=PREFIX,
        strategy_id=STRATEGY,
        admission=admission(historical_state),
        qualification=qualification(qualification_state),
        effective_paper_entry_allowed=effective_paper_entry_allowed,
        evaluated_at=diag.evaluated_at,
    )
def test_multi_open_records_every_executable_signal(tmp_path: Path) -> None:
    advance(
        tmp_path,
        diag=diagnostic(0),
        qualification_state=ProspectiveQualificationState.COLLECTING,
        bars=[],
    )
    advance(
        tmp_path,
        diag=diagnostic(5),
        qualification_state=ProspectiveQualificationState.COLLECTING,
        bars=[],
    )

    import json

    payload = json.loads(
        (tmp_path / f"{PREFIX}_authority_regret_state.json").read_text()
    )
    assert len(payload["open_records"]) == 2
    assert payload["open_records"][0]["trade"]["trade_id"] != (
        payload["open_records"][1]["trade"]["trade_id"]
    )


def test_locked_winner_is_counted_as_missed_and_snapshot_is_frozen(
    tmp_path: Path,
) -> None:
    first = diagnostic(0)
    advance(
        tmp_path,
        diag=first,
        qualification_state=ProspectiveQualificationState.COLLECTING,
        bars=[],
    )

    # Qualification changes later, but the original signal remains locked.
    advance(
        tmp_path,
        diag=first,
        qualification_state=ProspectiveQualificationState.SUPPORTS_DEMO,
        bars=[bar(10, high=101.2)],
    )

    records = load_authority_regret_records(
        tmp_path / f"{PREFIX}_authority_regret.jsonl"
    )
    assert len(records) == 1
    assert records[0].outcome == AuthorityRegretOutcome.LOCKED_WINNER_MISSED
    assert (
        records[0].authority.prospective_state
        == ProspectiveQualificationState.COLLECTING
    )

    summary = build_authority_regret_summary(tmp_path)
    assert summary.locked_winners_missed == 1
    assert summary.missed_winner_r == 1.0
    assert summary.net_authority_regret_r == 1.0
def test_locked_loss_is_counted_as_avoided(tmp_path: Path) -> None:
    diag = diagnostic(0)
    advance(
        tmp_path,
        diag=diag,
        qualification_state=ProspectiveQualificationState.COLLECTING,
        bars=[],
    )
    advance(
        tmp_path,
        diag=diag,
        qualification_state=ProspectiveQualificationState.COLLECTING,
        bars=[bar(10, high=100.5, low=99.0)],
    )

    summary = build_authority_regret_summary(tmp_path)
    assert summary.locked_losses_avoided == 1
    assert summary.avoided_loss_r == 1.0
    assert summary.net_authority_regret_r == -1.0


def test_supported_strategy_records_authorized_winner(tmp_path: Path) -> None:
    diag = diagnostic(0)
    advance(
        tmp_path,
        diag=diag,
        qualification_state=ProspectiveQualificationState.SUPPORTS_DEMO,
        bars=[],
        historical_state=AdmissionState.ACTIVE,
    )
    advance(
        tmp_path,
        diag=diag,
        qualification_state=ProspectiveQualificationState.SUPPORTS_DEMO,
        bars=[bar(10, high=101.2)],
        historical_state=AdmissionState.ACTIVE,
    )

    summary = build_authority_regret_summary(tmp_path)
    assert summary.authorized_winners == 1
    assert summary.authorized_total_r == 1.0
    assert summary.broker_authority_changed is False


def test_entry_disable_does_not_start_new_regret_trade(tmp_path: Path) -> None:
    diag = diagnostic(0)
    advance_authority_regret_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        runtime_dir=tmp_path,
        prefix=PREFIX,
        strategy_id=STRATEGY,
        admission=admission(),
        qualification=qualification(ProspectiveQualificationState.COLLECTING),
        effective_paper_entry_allowed=True,
        evaluated_at=diag.evaluated_at,
        allow_new_entries=False,
    )
    summary = build_authority_regret_summary(tmp_path)
    assert summary.open_trades == 0
    assert summary.resolved == 0
