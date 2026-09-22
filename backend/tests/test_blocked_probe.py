from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.shadow_paper import PaperTradeStatus
from app.domain.trading import Side
from app.services.blocked_probe import (
    advance_blocked_probe_book,
    create_blocked_probe,
    load_blocked_probe_summary,
    resolve_open_probe,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 21, 8, 10, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4355.0,
        ask=4355.3,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100,
        lot_step=0.01,
        margin_required=380,
    )


def diagnostic(
    *,
    max_risk_approved: bool = True,
) -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        evaluated_at=START + timedelta(minutes=5, seconds=2),
        latest_closed_m5_at=START,
        latest_closed_m15_at=START - timedelta(minutes=15),
        state=ShadowSignalState.SIGNAL_BLOCKED,
        side=Side.BUY,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=7.2,
        atr_ratio=1,
        volatility_percentile=0.5,
        efficiency=0.3,
        structural_stop=4352.3,
        target_r=1.5,
        max_holding_bars=12,
        base_risk=ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=False,
            reason="minimum broker lot exceeds the risk budget",
            lots=0,
            expected_loss_eur=0,
            spread_to_stop=0.1,
        ),
        max_risk=ShadowSizingSnapshot(
            risk_fraction=0.02,
            approved=max_risk_approved,
            reason=(
                "risk and execution constraints satisfied"
                if max_risk_approved
                else "spread consumes too much of the stop distance"
            ),
            lots=0.01 if max_risk_approved else 0,
            expected_loss_eur=3.0 if max_risk_approved else 0,
            spread_to_stop=0.1,
        ),
        reason="blocked setup",
    )


def bar(
    index: int,
    *,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * (index + 1)),
        open=4355.3,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def test_blocked_probe_preserves_base_reason_and_max_risk_viability() -> None:
    probe = create_blocked_probe(
        diagnostic=diagnostic(max_risk_approved=True),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )

    assert probe.block_reason == "minimum broker lot exceeds the risk budget"
    assert probe.max_risk_approved is True
    assert probe.target_r == 1.5
    assert probe.min_lot_loss_eur == 3.0
    assert probe.required_capital_base_risk_eur == 300.0
    assert probe.required_capital_max_risk_eur == 150.0
    assert probe.minimum_feasible_risk_fraction == 0.0075
    assert probe.capital_granularity_feasible_under_max_risk is True


def test_blocked_probe_resolves_target_without_position_sizing() -> None:
    probe = create_blocked_probe(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )
    resolved = resolve_open_probe(
        probe,
        [
            bar(1, high=4355.8, low=4353.0, close=4355.0),
            bar(2, high=4359.9, low=4354.0, close=4359.0),
        ],
    )

    assert resolved.status == PaperTradeStatus.TARGET
    assert resolved.result_r == 1.5


def test_advance_blocked_probe_deduplicates_same_signal(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    probes_path = tmp_path / "probes.jsonl"
    diag = diagnostic()

    first = advance_blocked_probe_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        probes_path=probes_path,
        evaluated_at=diag.evaluated_at,
    )
    second = advance_blocked_probe_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        probes_path=probes_path,
        evaluated_at=diag.evaluated_at + timedelta(seconds=30),
    )

    assert first.open_probe is not None
    assert second.open_probe is not None
    assert first.open_probe.probe_id == second.open_probe.probe_id


def test_blocked_probe_summary_is_separate_from_paper_pnl(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    probes_path = tmp_path / "probes.jsonl"

    summary = load_blocked_probe_summary(state_path, probes_path)

    assert summary.closed_probes == 0
    assert summary.total_r == 0
    assert summary.open_probe is None


def test_existing_open_probe_is_enriched_with_capital_feasibility(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    probes_path = tmp_path / "probes.jsonl"
    diag = diagnostic(max_risk_approved=False)

    first = advance_blocked_probe_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        probes_path=probes_path,
        evaluated_at=diag.evaluated_at,
    )
    assert first.open_probe is not None

    legacy = first.open_probe.model_copy(
        update={
            "min_lot_loss_eur": 0.0,
            "required_capital_base_risk_eur": 0.0,
            "required_capital_max_risk_eur": 0.0,
            "minimum_feasible_risk_fraction": 0.0,
            "capital_granularity_feasible_under_max_risk": False,
        }
    )
    from app.domain.blocked_probe import BlockedProbeState
    from app.services.blocked_probe import save_blocked_probe_state

    save_blocked_probe_state(
        state_path,
        BlockedProbeState(
            last_started_signal_at=diag.latest_closed_m5_at + timedelta(minutes=5),
            open_probe=legacy,
        ),
    )

    second = advance_blocked_probe_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        probes_path=probes_path,
        evaluated_at=diag.evaluated_at + timedelta(seconds=30),
    )

    assert second.open_probe is not None
    assert second.open_probe.min_lot_loss_eur == 3.0
    assert second.open_probe.required_capital_max_risk_eur == 150.0
