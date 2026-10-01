from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.opportunity import OpportunityMechanism
from app.domain.opportunity_funnel import (
    ResearchProbeQualification,
    ResearchProbeQualificationState,
)
from app.domain.shadow_paper import ShadowPaperState, ShadowPaperTrade
from app.domain.trading import Side
from app.services.multi_shadow_collector import (
    collect_all_shadow_once,
    paper_entry_allowed,
    shadow_mechanism_enabled,
    should_advance_unqualified_probe,
    unqualified_probe_entry_allowed,
)
from app.services.paper_registry import _parse_state_name


def decision(
    state: AdmissionState,
    *,
    weakest_expectancy_r: float = 0.1,
    paper_collection_candidate: bool = False,
) -> AdmissionDecision:
    return AdmissionDecision(
        strategy_id="EURUSD:test",
        state=state,
        reason="test",
        weakest_expectancy_r=weakest_expectancy_r,
        worst_drawdown_r=1.0,
        paper_collection_candidate=paper_collection_candidate,
    )


def test_missing_admission_cannot_open_new_paper_trade() -> None:
    assert paper_entry_allowed(None) is False


def test_rejected_admission_cannot_open_new_paper_trade() -> None:
    assert paper_entry_allowed(decision(AdmissionState.REJECTED)) is False


def test_unqualified_probe_tracks_only_non_paper_admissions() -> None:
    assert unqualified_probe_entry_allowed(None) is True
    assert unqualified_probe_entry_allowed(decision(AdmissionState.REJECTED)) is True
    assert (
        unqualified_probe_entry_allowed(
            decision(AdmissionState.SHADOW, weakest_expectancy_r=-0.01)
        )
        is True
    )
    assert unqualified_probe_entry_allowed(decision(AdmissionState.SHADOW)) is False
    assert unqualified_probe_entry_allowed(decision(AdmissionState.ACTIVE)) is False


def test_unqualified_probe_continues_existing_state_after_promotion(tmp_path: Path) -> None:
    state_path = tmp_path / "existing_unqualified_probe_state.json"
    state_path.write_text("{}", encoding="utf-8")

    assert should_advance_unqualified_probe(decision(AdmissionState.ACTIVE), state_path) is True
    assert (
        should_advance_unqualified_probe(
            decision(AdmissionState.ACTIVE),
            tmp_path / "missing_state.json",
        )
        is False
    )



def test_unqualified_probe_state_is_not_a_paper_registry_state() -> None:
    assert (
        _parse_state_name(
            Path("BTCUSD_directional_transition_unqualified_probe_state.json")
        )
        is None
    )


def test_positive_shadow_admission_can_open_new_paper_trade() -> None:
    assert paper_entry_allowed(decision(AdmissionState.SHADOW)) is True


def test_negative_shadow_admission_cannot_open_new_paper_trade() -> None:
    assert (
        paper_entry_allowed(
            decision(
                AdmissionState.SHADOW,
                weakest_expectancy_r=-0.01,
            )
        )
        is False
    )


def test_zero_expectancy_shadow_admission_cannot_open_new_paper_trade() -> None:
    assert (
        paper_entry_allowed(
            decision(
                AdmissionState.SHADOW,
                weakest_expectancy_r=0.0,
            )
        )
        is False
    )


def test_active_admission_remains_paper_eligible() -> None:
    assert (
        paper_entry_allowed(
            decision(
                AdmissionState.ACTIVE,
                weakest_expectancy_r=0.2,
            )
        )
        is True
    )



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



def test_promising_shadow_can_collect_paper_despite_sparse_negative_holdout() -> None:
    assert (
        paper_entry_allowed(
            decision(
                AdmissionState.SHADOW,
                weakest_expectancy_r=-0.24,
                paper_collection_candidate=True,
            )
        )
        is True
    )


def test_rejected_strategy_never_collects_paper_even_if_candidate_flag_is_true() -> None:
    assert (
        paper_entry_allowed(
            decision(
                AdmissionState.REJECTED,
                weakest_expectancy_r=0.2,
                paper_collection_candidate=True,
            )
        )
        is False
    )


def test_parallel_paper_books_do_not_block_same_symbol_other_family(
    tmp_path: Path,
    monkeypatch,
) -> None:
    now = datetime(2026, 10, 1, 10, 0, tzinfo=ZoneInfo("Europe/Athens"))
    strategy_id = "XAUUSD:structural_displacement_sequence"
    admission = AdmissionDecision(
        strategy_id=strategy_id,
        state=AdmissionState.SHADOW,
        reason="under-sampled",
        weakest_expectancy_r=0.3,
        worst_drawdown_r=2.0,
        paper_collection_candidate=True,
    )

    # Another XAU family already owns an independent PAPER trade.
    existing_trade = ShadowPaperTrade(
        trade_id="existing-asia-paper",
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        side=Side.BUY,
        signal_at=now,
        entry_bar_at=now,
        opened_at=now,
        entry_price=4160.0,
        stop_price=4156.0,
        target_price=4166.0,
        spread_at_entry=0.28,
        lots=1.0,
        risk_eur=400.0,
        risk_distance=4.0,
        target_r=1.5,
        max_holding_bars=12,
    )
    (
        tmp_path / "XAUUSD_asia_range_sweep_paper_state.json"
    ).write_text(
        ShadowPaperState(open_trade=existing_trade).model_dump_json(),
        encoding="utf-8",
    )

    class FakeDiagnostic:
        latest_closed_m5_at = now

        def model_copy(self, *, update):
            return self

    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_research_admissions",
        lambda path: {strategy_id: admission},
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.build_market_universe",
        lambda *args, **kwargs: [
            SimpleNamespace(symbol="XAUUSD", paper_ready=True, quote_live=True)
        ],
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.get_mt4_symbol_spec",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_closed_market_bars",
        lambda *args, **kwargs: [object()] * 50,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.shadow_mechanism_enabled",
        lambda symbol, mechanism: (
            mechanism == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
        ),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.scan_shadow_opportunity",
        lambda *args, **kwargs: FakeDiagnostic(),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_macro_events",
        lambda path: [],
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.classify_macro_signal_context",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.append_shadow_observation",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.capture_xau_sequence_microstructure",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_research_probe_qualification",
        lambda *args, **kwargs: None,
    )

    def record_paper_call(*, state_path, allow_new_entries, **kwargs):
        calls.append((state_path.name, allow_new_entries))
        return SimpleNamespace()

    monkeypatch.setattr(
        "app.services.multi_shadow_collector.advance_shadow_paper_book",
        record_paper_call,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector."
        "advance_xau_structural_displacement_target_pair",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.advance_blocked_probe_book",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop")),
    )

    with pytest.raises(RuntimeError, match="stop"):
        collect_all_shadow_once(tmp_path, tmp_path, now)

    assert calls == [
        ("XAUUSD_structural_displacement_sequence_paper_state.json", True),
    ]


def test_probe_promotion_routes_signal_to_paper_and_stops_new_probe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    now = datetime(2026, 10, 1, 10, 0, tzinfo=ZoneInfo("Europe/Athens"))
    strategy_id = "XAUUSD:directional_transition"
    admission = AdmissionDecision(
        strategy_id=strategy_id,
        state=AdmissionState.SHADOW,
        reason="under-sampled",
        weakest_expectancy_r=0.0,
        worst_drawdown_r=0.0,
        paper_collection_candidate=False,
    )
    qualification = ResearchProbeQualification(
        state=ResearchProbeQualificationState.SUPPORTS_REVIEW,
        closed_trades=20,
        minimum_trades=20,
        expectancy_r=0.4,
        profit_factor=2.0,
        max_drawdown_r=2.0,
        reason="supports paper review",
    )

    class FakeDiagnostic:
        latest_closed_m5_at = now

        def model_copy(self, *, update):
            return self

    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_research_admissions",
        lambda path: {strategy_id: admission},
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.build_market_universe",
        lambda *args, **kwargs: [
            SimpleNamespace(symbol="XAUUSD", paper_ready=True, quote_live=True)
        ],
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.get_mt4_symbol_spec",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_closed_market_bars",
        lambda *args, **kwargs: [object()] * 50,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.shadow_mechanism_enabled",
        lambda symbol, mechanism: (
            mechanism == OpportunityMechanism.DIRECTIONAL_TRANSITION
        ),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.scan_shadow_opportunity",
        lambda *args, **kwargs: FakeDiagnostic(),
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_macro_events",
        lambda path: [],
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.classify_macro_signal_context",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.append_shadow_observation",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.capture_xau_sequence_microstructure",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.load_research_probe_qualification",
        lambda *args, **kwargs: qualification,
    )

    def record_paper_call(*, state_path, allow_new_entries, **kwargs):
        calls.append((state_path.name, allow_new_entries))
        return SimpleNamespace()

    monkeypatch.setattr(
        "app.services.multi_shadow_collector.advance_shadow_paper_book",
        record_paper_call,
    )
    monkeypatch.setattr(
        "app.services.multi_shadow_collector.advance_blocked_probe_book",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop")),
    )

    with pytest.raises(RuntimeError, match="stop"):
        collect_all_shadow_once(tmp_path, tmp_path, now)

    assert calls == [
        ("XAUUSD_directional_transition_paper_state.json", True),
        ("XAUUSD_directional_transition_unqualified_probe_state.json", False),
    ]
