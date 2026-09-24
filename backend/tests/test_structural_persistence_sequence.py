from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.admission import AdmissionState, EvidenceWindow, StrategyEvidence
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.admission import assess_strategy, paper_entry_allowed
from app.services.blocked_probe_registry import _parse_state_name as parse_probe_state
from app.services.multi_shadow_collector import shadow_mechanism_enabled
from app.services.opportunity_strategies import (
    _structural_persistence_sequence_candidate,
    _structural_persistence_sequence_side,
    _structural_persistence_sequence_signal,
)
from app.services.paper_registry import _parse_state_name as parse_paper_state


def _bars(symbol: str = "XAUUSD", count: int = 30) -> list[MarketBar]:
    start = datetime(2026, 6, 1, tzinfo=UTC)
    return [
        MarketBar(
            symbol=symbol,
            timeframe=Timeframe.M5,
            timestamp=start + timedelta(minutes=5 * index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=100,
        )
        for index in range(count)
    ]


def _fake_context(*, index: int, **kwargs) -> OpportunityCausalContext:
    if index == 24:
        return OpportunityCausalContext(
            pattern=OpportunityCausalPattern.DIRECTIONAL_DISPLACEMENT,
            side=Side.SELL,
        )
    if index in {25, 26}:
        return OpportunityCausalContext(
            pattern=OpportunityCausalPattern.STRUCTURAL_EXTREME,
        )
    return OpportunityCausalContext()


def test_persistence_sequence_inherits_latest_directional_side(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.opportunity_strategies._classify_causal_context",
        _fake_context,
    )
    bars = _bars()
    atr = [2.0] * len(bars)

    assert _structural_persistence_sequence_side(bars, atr, 26) == Side.SELL


def test_persistence_sequence_is_xau_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.opportunity_strategies._classify_causal_context",
        _fake_context,
    )
    atr = [2.0] * 30
    mechanism = OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE

    assert _structural_persistence_sequence_side(_bars("XAUUSD"), atr, 26) == Side.SELL
    assert _structural_persistence_sequence_side(_bars("BTCUSD"), atr, 26) is None
    assert shadow_mechanism_enabled("XAUUSD", mechanism) is True
    assert shadow_mechanism_enabled("BTCUSD", mechanism) is False
    assert shadow_mechanism_enabled("EURUSD", mechanism) is False
    assert shadow_mechanism_enabled("GBPUSD", mechanism) is False
    assert shadow_mechanism_enabled("XAGUSD", mechanism) is False


def test_persistence_runtime_and_backtest_geometry_are_identical(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.opportunity_strategies._classify_causal_context",
        _fake_context,
    )
    bars = _bars()
    atr = [2.0] * len(bars)

    candidate = _structural_persistence_sequence_candidate(bars, atr, 26)
    signal = _structural_persistence_sequence_signal(bars[:27], atr[:27])

    assert candidate is not None
    assert signal is not None
    assert candidate.mechanism == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE
    assert candidate.side == signal[0] == Side.SELL
    assert candidate.structural_stop == bars[27].open + 3.0
    assert candidate.target_r == signal[2] == 1.0
    assert candidate.max_holding_bars == signal[3] == 12
    assert signal[4] == 3.0


def test_persistence_candidate_does_not_use_future_bars(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.opportunity_strategies._classify_causal_context",
        _fake_context,
    )
    bars = _bars()
    atr = [2.0] * len(bars)
    first = _structural_persistence_sequence_candidate(bars, atr, 26)

    changed = list(bars)
    changed[29] = changed[29].model_copy(
        update={"high": 1000.0, "low": 1.0, "close": 999.0}
    )
    second = _structural_persistence_sequence_candidate(changed, atr, 26)

    assert first is not None and second is not None
    assert second.side == first.side
    assert second.structural_stop == first.structural_stop


def test_persistence_registry_parsing() -> None:
    expected = (
        "XAUUSD",
        OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE,
        "XAUUSD_structural_persistence_sequence",
    )
    assert parse_paper_state(
        Path("XAUUSD_structural_persistence_sequence_paper_state.json")
    ) == expected
    assert parse_probe_state(
        Path("XAUUSD_structural_persistence_sequence_blocked_probe_state.json")
    ) == expected


def test_persistence_adds_exactly_one_runtime_scanner() -> None:
    symbols = ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD")
    enabled = [
        (symbol, mechanism)
        for symbol in symbols
        for mechanism in OpportunityMechanism
        if shadow_mechanism_enabled(symbol, mechanism)
    ]

    assert len(enabled) == 26
    persistence_rows = [
        row
        for row in enabled
        if row[1] == OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE
    ]
    assert persistence_rows == [
        ("XAUUSD", OpportunityMechanism.STRUCTURAL_PERSISTENCE_SEQUENCE)
    ]


def test_persistence_incremental_evidence_is_shadow_paper_candidate() -> None:
    evidence = StrategyEvidence(
        strategy_id="XAUUSD:structural_persistence_sequence",
        train=EvidenceWindow(
            trades=79,
            expectancy_r=0.0448507063,
            profit_factor=1.1051605452,
            max_drawdown_r=6.5478581933,
        ),
        validation=EvidenceWindow(
            trades=27,
            expectancy_r=0.0528699329,
            profit_factor=1.1278327670,
            max_drawdown_r=6.0460035839,
        ),
        holdout=EvidenceWindow(
            trades=16,
            expectancy_r=0.0392269633,
            profit_factor=1.0851329401,
            max_drawdown_r=2.3723685869,
        ),
    )

    decision = assess_strategy(evidence)

    assert decision.state == AdmissionState.SHADOW
    assert decision.paper_collection_candidate is True
    assert decision.weakest_expectancy_r > 0
    assert paper_entry_allowed(decision) is True
