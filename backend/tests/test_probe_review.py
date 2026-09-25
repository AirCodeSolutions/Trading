from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import app.services.probe_review as probe_review_service
from app.domain.opportunity import OpportunityMechanism, ResearchSplit
from app.domain.opportunity_funnel import (
    ResearchProbeQualification,
    ResearchProbeQualificationState,
)
from app.domain.trading_intelligence import (
    AdmittedTradeEarlyContextSummary,
    BlockedProbeEarlyContextSummary,
    OpportunityWaitingSummary,
    ProbeEarlyContextSummary,
)
from app.services.probe_review import (
    _parse_strategy_id,
    build_probe_review_pack,
    default_probe_review_contract,
    default_probe_review_split,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 23, 16, 0, tzinfo=TZ)
SPLIT = ResearchSplit(
    train_end=datetime(2026, 7, 1, tzinfo=TZ),
    validation_end=datetime(2026, 9, 1, tzinfo=TZ),
)


def test_probe_review_pack_refuses_strategy_without_supports_review(
    tmp_path: Path,
) -> None:
    pack = build_probe_review_pack(
        tmp_path,
        tmp_path,
        strategy_id="BTCUSD:directional_transition",
        now=NOW,
        split=SPLIT,
    )

    assert pack.review_ready is False
    assert pack.probe_qualification is None
    assert pack.historical_admission is None
    assert "not SUPPORTS_REVIEW" in pack.reason
    assert pack.requires_human_decision is True


def test_probe_review_strategy_id_parser_is_strict() -> None:
    symbol, mechanism = _parse_strategy_id("xauusd:failed_auction_reversal")
    assert symbol == "XAUUSD"
    assert mechanism.value == "failed_auction_reversal"

    with pytest.raises(ValueError, match="SYMBOL:mechanism"):
        _parse_strategy_id("bad")


def test_probe_review_pack_attaches_economic_evidence_when_review_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    strategy_id = "BTCUSD:directional_transition"
    mechanism = OpportunityMechanism.DIRECTIONAL_TRANSITION
    qualification = ResearchProbeQualification(
        state=ResearchProbeQualificationState.SUPPORTS_REVIEW,
        closed_trades=20,
        minimum_trades=20,
        expectancy_r=0.25,
        profit_factor=1.5,
        max_drawdown_r=3.0,
        reason="prospective probes support review",
    )
    queue_item = SimpleNamespace(
        strategy_id=strategy_id,
        qualification=qualification,
    )
    probe_context = ProbeEarlyContextSummary(
        strategy_id=strategy_id,
        symbol="BTCUSD",
        mechanism=mechanism,
        resolved_probes=20,
        m1_eligible_probes=12,
        tick_pressure_eligible_probes=8,
        tick_pressure_wins=5,
        tick_pressure_losses=3,
        tick_pressure_total_r=4.0,
        tick_pressure_expectancy_r=0.5,
    )
    waiting_cost = OpportunityWaitingSummary(
        strategy_id=strategy_id,
        symbol="BTCUSD",
        mechanism=mechanism,
        episodes_with_signal=10,
        executable_signals=8,
        blocked_signals=2,
        precursor_then_signal_episodes=6,
        average_signal_lead_lag_minutes=4.0,
        average_move_atr=1.6,
        average_move_consumed_at_signal_atr=0.5,
        average_move_remaining_after_signal_atr=1.1,
        average_move_consumed_fraction=0.3125,
        average_precursor_to_signal_minutes=3.0,
    )
    admitted_context = AdmittedTradeEarlyContextSummary(
        strategy_id=strategy_id,
        symbol="BTCUSD",
        mechanism=mechanism,
        resolved_trades=2,
        m1_eligible_trades=2,
        tick_pressure_eligible_trades=2,
        tick_pressure_wins=1,
        tick_pressure_losses=1,
        tick_pressure_total_r=0.8,
        tick_pressure_expectancy_r=0.4,
    )
    blocked_context = BlockedProbeEarlyContextSummary(
        strategy_id=strategy_id,
        symbol="BTCUSD",
        mechanism=mechanism,
        block_reason="spread consumes too much of the stop distance",
        resolved_blocked_probes=3,
        m1_eligible_probes=2,
        tick_pressure_eligible_probes=1,
        wins=0,
        losses=1,
        total_r=-1.0,
        expectancy_r=-1.0,
        median_spread_to_risk=0.2,
        median_path_efficiency_5m=0.3,
    )
    intelligence = SimpleNamespace(
        probe_early_context=SimpleNamespace(summaries=[probe_context]),
        waiting_costs=[waiting_cost],
        waiting_early_context=None,
        admitted_trade_early_context=SimpleNamespace(
            summaries=[admitted_context]
        ),
        blocked_probe_early_context=SimpleNamespace(
            summaries=[blocked_context]
        ),
    )

    monkeypatch.setattr(
        probe_review_service,
        "build_opportunity_funnel",
        lambda *args, **kwargs: SimpleNamespace(
            unqualified_probe_review_queue=[queue_item]
        ),
    )
    monkeypatch.setattr(
        probe_review_service,
        "build_trading_intelligence",
        lambda *args, **kwargs: intelligence,
    )
    monkeypatch.setattr(
        probe_review_service,
        "run_mt4_portfolio_research",
        lambda *args, **kwargs: SimpleNamespace(results=[]),
    )

    pack = build_probe_review_pack(
        tmp_path,
        tmp_path,
        strategy_id=strategy_id,
        now=NOW,
        split=SPLIT,
    )

    assert pack.review_ready is True
    assert pack.evidence_window_hours == 168
    assert pack.prospective_probe_context == probe_context
    assert pack.waiting_cost_context == waiting_cost
    assert pack.waiting_early_context is None
    assert pack.admitted_trade_context == admitted_context
    assert pack.blocked_probe_contexts == [blocked_context]
    assert pack.historical_admission is None
    assert pack.requires_human_decision is True


def test_default_probe_review_contract_matches_split() -> None:
    contract = default_probe_review_contract()
    split = default_probe_review_split()

    assert contract.timezone == "Europe/Athens"
    assert contract.evidence_window_hours == 168
    assert contract.train_end.isoformat() == "2026-07-01T00:00:00+03:00"
    assert contract.validation_end.isoformat() == "2026-09-01T00:00:00+03:00"
    assert split.train_end == contract.train_end
    assert split.validation_end == contract.validation_end
