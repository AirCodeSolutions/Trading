from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.blocked_probe import BlockedOpportunityProbe, BlockedProbeState
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_funnel import ResearchProbeQualificationState
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperState, ShadowPaperTrade
from app.domain.trading import Side
from app.main import app
from app.services.opportunity_funnel import build_opportunity_funnel

NOW = datetime(2026, 9, 22, 7, 30, tzinfo=UTC)


def diagnostic(
    *,
    symbol: str,
    mechanism: OpportunityMechanism,
    at: datetime,
    state: ShadowSignalState,
    reason: str = "test",
) -> ShadowOpportunityDiagnostic:
    sizing = None
    side = None
    stop = None
    target_r = None
    if state != ShadowSignalState.NO_SIGNAL:
        side = Side.BUY
        stop = 99.0
        target_r = 1.5
        sizing = ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=state == ShadowSignalState.SIGNAL_EXECUTABLE,
            reason=reason,
            lots=0.0 if state == ShadowSignalState.SIGNAL_BLOCKED else 0.01,
            expected_loss_eur=0.0 if state == ShadowSignalState.SIGNAL_BLOCKED else 2.0,
            spread_to_stop=0.1,
        )
    return ShadowOpportunityDiagnostic(
        symbol=symbol,
        mechanism=mechanism,
        evaluated_at=at,
        latest_closed_m5_at=at - timedelta(minutes=5),
        latest_closed_m15_at=at - timedelta(minutes=15),
        state=state,
        side=side,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=1,
        atr_ratio=1,
        volatility_percentile=0.5,
        efficiency=0.4,
        structural_stop=stop,
        target_r=target_r,
        base_risk=sizing,
        reason=reason,
    )


def write_diagnostics(path: Path, rows: list[ShadowOpportunityDiagnostic]) -> None:
    path.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )


def blocked_probe(
    *,
    probe_id: str,
    signal_at: datetime,
    result_r: float | None,
    status: PaperTradeStatus,
    min_lot_loss_eur: float = 3.0,
    required_capital_eur: float = 300.0,
    feasible_under_max: bool = True,
) -> BlockedOpportunityProbe:
    return BlockedOpportunityProbe(
        probe_id=probe_id,
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        side=Side.SELL,
        signal_at=signal_at,
        opened_at=signal_at,
        entry_price=100.0,
        stop_price=101.0,
        target_price=98.2,
        spread_at_entry=0.1,
        risk_distance=1.0,
        target_r=1.8,
        max_holding_bars=18,
        block_reason="minimum broker lot exceeds the risk budget",
        max_risk_approved=feasible_under_max,
        max_risk_reason="test",
        min_lot_loss_eur=min_lot_loss_eur,
        required_capital_base_risk_eur=required_capital_eur,
        required_capital_max_risk_eur=required_capital_eur / 2,
        minimum_feasible_risk_fraction=min_lot_loss_eur / 200.0,
        capital_granularity_feasible_under_max_risk=feasible_under_max,
        status=status,
        exit_at=signal_at + timedelta(minutes=10) if result_r is not None else None,
        exit_price=98.2 if result_r and result_r > 0 else 101.0 if result_r is not None else None,
        result_r=result_r,
        bars_held=2 if result_r is not None else 0,
    )


def unqualified_probe(
    trade_id: str,
    signal_at: datetime,
    result_r: float | None,
    status: PaperTradeStatus,
) -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id=trade_id,
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        side=Side.SELL,
        signal_at=signal_at,
        entry_bar_at=signal_at,
        opened_at=signal_at,
        entry_price=100.0,
        stop_price=101.0,
        target_price=98.5,
        spread_at_entry=0.1,
        lots=0.01,
        risk_eur=2.0,
        risk_distance=1.0,
        target_r=1.5,
        max_holding_bars=18,
        status=status,
        exit_at=signal_at + timedelta(minutes=10) if result_r is not None else None,
        exit_price=98.5 if result_r and result_r > 0 else 101.0 if result_r is not None else None,
        result_r=result_r,
        pnl_eur=result_r * 2.0 if result_r is not None else None,
        bars_held=2 if result_r is not None else 0,
    )


def test_funnel_counts_signals_in_window_and_block_reasons(tmp_path: Path) -> None:
    write_diagnostics(
        tmp_path / "BTCUSD_directional_transition.jsonl",
        [
            diagnostic(
                symbol="BTCUSD",
                mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
                at=NOW - timedelta(hours=30),
                state=ShadowSignalState.SIGNAL_BLOCKED,
                reason="outside",
            ),
            diagnostic(
                symbol="BTCUSD",
                mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
                at=NOW - timedelta(hours=3),
                state=ShadowSignalState.NO_SIGNAL,
            ),
            diagnostic(
                symbol="BTCUSD",
                mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
                at=NOW - timedelta(hours=2),
                state=ShadowSignalState.SIGNAL_BLOCKED,
                reason="minimum broker lot exceeds the risk budget",
            ),
            diagnostic(
                symbol="BTCUSD",
                mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
                at=NOW - timedelta(hours=1),
                state=ShadowSignalState.SIGNAL_EXECUTABLE,
            ),
        ],
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
    )

    assert funnel.signal_rows == 2
    assert funnel.blocked_signal_rows == 1
    assert funnel.executable_signal_rows == 1
    assert funnel.block_reasons == {
        "minimum broker lot exceeds the risk budget": 1
    }
    assert len(funnel.strategies) == 1
    assert funnel.strategies[0].signal_rows == 2


def test_funnel_aggregates_unqualified_executable_probes(tmp_path: Path) -> None:
    closed = [
        unqualified_probe(
            "u1", NOW - timedelta(hours=4), 1.5, PaperTradeStatus.TARGET
        ),
        unqualified_probe(
            "u2", NOW - timedelta(hours=2), -1.0, PaperTradeStatus.STOP
        ),
    ]
    (tmp_path / "BTCUSD_directional_transition_unqualified_probes.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in closed),
        encoding="utf-8",
    )
    open_probe = unqualified_probe(
        "u3", NOW - timedelta(minutes=30), None, PaperTradeStatus.OPEN
    )
    (
        tmp_path / "BTCUSD_directional_transition_unqualified_probe_state.json"
    ).write_text(
        ShadowPaperState(open_trade=open_probe).model_dump_json(),
        encoding="utf-8",
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
    )

    assert funnel.tracked_unqualified_probes == 3
    assert funnel.resolved_unqualified_probes == 2
    assert funnel.open_unqualified_probes == 1
    assert funnel.unqualified_probe_wins == 1
    assert funnel.unqualified_probe_losses == 1
    assert funnel.unqualified_probe_total_r == 0.5
    assert funnel.unqualified_probe_expectancy_r == 0.25
    assert funnel.strategies[0].tracked_unqualified_probes == 3
    qualification = funnel.strategies[0].unqualified_probe_qualification
    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.COLLECTING
    assert qualification.closed_trades == 2
    assert qualification.minimum_trades == 20
    assert qualification.reason == (
        "2/20 resolved executable probes; minimum research-review sample not reached"
    )
    candidate = funnel.most_observed_unqualified_candidate
    assert candidate is not None
    assert candidate.strategy_id == "BTCUSD:directional_transition"
    assert candidate.symbol == "BTCUSD"
    assert candidate.mechanism == OpportunityMechanism.DIRECTIONAL_TRANSITION
    assert candidate.qualification.closed_trades == 2
    assert funnel.unqualified_probe_review_ready_strategies == 0


def test_funnel_marks_positive_probe_evidence_for_review(tmp_path: Path) -> None:
    closed = [
        unqualified_probe(
            f"positive-{index}",
            NOW - timedelta(minutes=5 * (20 - index)),
            1.5,
            PaperTradeStatus.TARGET,
        )
        for index in range(20)
    ]
    (tmp_path / "BTCUSD_directional_transition_unqualified_probes.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in closed),
        encoding="utf-8",
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
    )

    qualification = funnel.strategies[0].unqualified_probe_qualification
    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.SUPPORTS_REVIEW
    assert qualification.closed_trades == 20
    assert qualification.expectancy_r == 1.5
    assert qualification.profit_factor == 99.0
    assert funnel.unqualified_probe_review_ready_strategies == 1


def test_funnel_marks_negative_probe_evidence_failed(tmp_path: Path) -> None:
    closed = [
        unqualified_probe(
            f"negative-{index}",
            NOW - timedelta(minutes=5 * (20 - index)),
            -1.0,
            PaperTradeStatus.STOP,
        )
        for index in range(20)
    ]
    (tmp_path / "BTCUSD_directional_transition_unqualified_probes.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in closed),
        encoding="utf-8",
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
    )

    qualification = funnel.strategies[0].unqualified_probe_qualification
    assert qualification is not None
    assert qualification.state == ResearchProbeQualificationState.FAILED
    assert qualification.closed_trades == 20
    assert qualification.expectancy_r == -1.0
    assert "executable-probe" in qualification.reason
    assert funnel.unqualified_probe_review_ready_strategies == 0


def test_funnel_aggregates_closed_and_open_blocked_probes(tmp_path: Path) -> None:
    closed = [
        blocked_probe(
            probe_id="p1",
            signal_at=NOW - timedelta(hours=4),
            result_r=1.8,
            status=PaperTradeStatus.TARGET,
            min_lot_loss_eur=3.0,
            required_capital_eur=300.0,
        ),
        blocked_probe(
            probe_id="p2",
            signal_at=NOW - timedelta(hours=2),
            result_r=-1.0,
            status=PaperTradeStatus.STOP,
            min_lot_loss_eur=2.2,
            required_capital_eur=220.0,
        ),
    ]
    (tmp_path / "BTCUSD_directional_transition_blocked_probes.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in closed),
        encoding="utf-8",
    )
    open_probe = blocked_probe(
        probe_id="p3",
        signal_at=NOW - timedelta(minutes=30),
        result_r=None,
        status=PaperTradeStatus.OPEN,
        min_lot_loss_eur=2.1,
        required_capital_eur=210.0,
    )
    (tmp_path / "BTCUSD_directional_transition_blocked_probe_state.json").write_text(
        BlockedProbeState(open_probe=open_probe).model_dump_json(),
        encoding="utf-8",
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
    )

    assert funnel.tracked_blocked_probes == 3
    assert funnel.resolved_blocked_probes == 2
    assert funnel.open_blocked_probes == 1
    assert funnel.blocked_wins == 1
    assert funnel.blocked_losses == 1
    assert funnel.blocked_total_r == 0.8
    assert funnel.blocked_expectancy_r == 0.4
    assert funnel.blocked_feasible_under_max_risk == 3
    strategy = funnel.strategies[0]
    assert strategy.min_required_capital_base_risk_eur == 210.0
    assert strategy.max_required_capital_base_risk_eur == 300.0


def test_opportunity_funnel_api_is_read_only_and_uses_runtime_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shadow_ledger_dir", tmp_path)
    monkeypatch.setattr(settings, "session_watch_symbols", ("BTCUSD",))

    response = TestClient(app).get("/api/v1/shadow/opportunity-funnel?hours=24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 24
    assert payload["signal_rows"] == 0
    assert payload["tracked_blocked_probes"] == 0

def test_funnel_recomputes_capital_feasibility_for_current_reference(
    tmp_path: Path,
) -> None:
    probes = [
        blocked_probe(
            probe_id="base-win",
            signal_at=NOW - timedelta(hours=3),
            result_r=1.5,
            status=PaperTradeStatus.TARGET,
            min_lot_loss_eur=3.8,
            required_capital_eur=380.0,
            feasible_under_max=False,
        ),
        blocked_probe(
            probe_id="max-only-loss",
            signal_at=NOW - timedelta(hours=2),
            result_r=-1.0,
            status=PaperTradeStatus.STOP,
            min_lot_loss_eur=6.0,
            required_capital_eur=600.0,
            feasible_under_max=False,
        ),
        blocked_probe(
            probe_id="above-max",
            signal_at=NOW - timedelta(hours=1),
            result_r=1.5,
            status=PaperTradeStatus.TARGET,
            min_lot_loss_eur=9.0,
            required_capital_eur=900.0,
            feasible_under_max=False,
        ),
    ]
    (tmp_path / "BTCUSD_directional_transition_blocked_probes.jsonl").write_text(
        "".join(row.model_dump_json() + "\n" for row in probes),
        encoding="utf-8",
    )

    funnel = build_opportunity_funnel(
        tmp_path,
        now=NOW,
        window_hours=24,
        symbols=("BTCUSD",),
        reference_capital_eur=400.0,
        base_risk_fraction=0.01,
        absolute_max_risk_fraction=0.02,
    )

    assert funnel.reference_capital_eur == 400.0
    assert funnel.base_risk_budget_eur == 4.0
    assert funnel.absolute_max_risk_budget_eur == 8.0
    assert funnel.capital_limited_probes == 3
    assert funnel.capital_base_feasible_probes == 1
    assert funnel.capital_max_feasible_probes == 2
    assert funnel.capital_base_feasible_resolved_probes == 1
    assert funnel.capital_base_feasible_wins == 1
    assert funnel.capital_base_feasible_losses == 0
    assert funnel.capital_base_feasible_total_r == 1.5
    assert funnel.capital_base_feasible_expectancy_r == 1.5
    assert funnel.blocked_feasible_under_max_risk == 2
    strategy = funnel.strategies[0]
    assert strategy.capital_limited_probes == 3
    assert strategy.capital_base_feasible_probes == 1
    assert strategy.capital_base_feasible_total_r == 1.5
