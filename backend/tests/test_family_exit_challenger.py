from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism, TradeOutcome
from app.domain.runtime_capital import RuntimeCapitalSnapshot, RuntimeCapitalSource
from app.domain.trading import Side
from app.services.family_exit_challenger import (
    CHALLENGER_TARGET_R,
    CHAMPION_TARGET_R,
    HYPOTHESIS_ID,
    MAX_HOLDING_BARS,
    build_xau_structural_displacement_exit_challenger,
)

TZ = ZoneInfo("Europe/Athens")
VAL_AT = datetime(2026, 8, 1, 12, 0, tzinfo=TZ)
HOLD_AT = datetime(2026, 9, 10, 12, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD", bid=100.0, ask=100.2, tick_size=0.01,
        tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01,
        margin_required=10.0,
    )


def candidate(signal_at: datetime, index: int) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=signal_at,
        entry_at=signal_at,
        signal_index=index,
        entry_index=index,
        structural_stop=99.0,
        target_r=1.5,
        max_holding_bars=12,
        reason="paired exit test",
    )


def outcome(c: OpportunityCandidate, result_r: float) -> TradeOutcome:
    return TradeOutcome(
        symbol=c.symbol,
        mechanism=c.mechanism,
        side=c.side,
        signal_at=c.signal_at,
        entry_at=c.entry_at,
        exit_at=c.entry_at + timedelta(minutes=5),
        lots=1.0,
        risk_eur=100.0,
        result_r=result_r,
        pnl_eur=result_r * 100.0,
        execution_cost_r=0.05,
        exit_reason="target" if result_r > 0 else "stop",
    )


def test_p2b_contract_is_single_axis_and_preregistered() -> None:
    assert HYPOTHESIS_ID == "xau_sd_fixed_target_1_5r_vs_2r_exit_v1"
    assert CHAMPION_TARGET_R == 1.5
    assert CHALLENGER_TARGET_R == 2.0
    assert MAX_HOLDING_BARS == 12


def test_report_pairs_same_signals_and_changes_only_target(tmp_path: Path, monkeypatch) -> None:
    import app.services.family_exit_challenger as service

    validation = candidate(VAL_AT, 1)
    holdout = candidate(HOLD_AT, 20)
    bars = [
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=VAL_AT, open=100, high=101, low=99, close=100.5, volume=1),
        MarketBar(symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=HOLD_AT, open=100, high=101, low=99, close=100.5, volume=1),
    ]
    monkeypatch.setattr(service, "resolve_demo_sizing_capital", lambda _: RuntimeCapitalSnapshot(capital_eur=123456.0, source=RuntimeCapitalSource.BROKER_EQUITY, is_demo=True))
    monkeypatch.setattr(service, "get_mt4_symbol_spec", lambda *_: spec())
    monkeypatch.setattr(service, "load_research_execution_model", lambda _: None)
    monkeypatch.setattr(service, "resolve_mt4_history_path", lambda *args: tmp_path / "bars.csv")
    monkeypatch.setattr(service, "read_mt4_csv", lambda *args: bars)
    monkeypatch.setattr(service, "load_macro_events", lambda _: [])
    monkeypatch.setattr(service, "generate_candidates", lambda *args: [validation, holdout])
    monkeypatch.setattr(service, "active_macro_blackouts", lambda *args: [])

    seen = []
    def fake_simulate(_bars, c, _config):
        seen.append((c.signal_at, c.entry_index, c.structural_stop, c.target_r, c.max_holding_bars))
        result = 1.5 if c.target_r == 1.5 else 2.0
        return outcome(c, result), c.entry_index, None
    monkeypatch.setattr(service, "_simulate_candidate", fake_simulate)

    report = build_xau_structural_displacement_exit_challenger(
        tmp_path,
        generated_at=datetime(2026, 10, 1, 16, 0, tzinfo=TZ),
        risk_fraction=0.01,
        research_execution_model_path=tmp_path / "model.json",
        macro_events_path=tmp_path / "macro.json",
    )

    assert report.capital_eur == 123456.0
    assert report.validation.paired_trades == 1
    assert report.holdout.paired_trades == 1
    assert report.validation.delta_total_r == 0.5
    assert report.holdout.delta_total_r == 0.5
    assert report.authority_effect is False
    assert report.human_review_required is True
    assert len(seen) == 4
    for champion, challenger in zip(seen[::2], seen[1::2], strict=True):
        assert champion[:3] == challenger[:3]
        assert champion[4] == challenger[4] == 12
        assert champion[3] == 1.5
        assert challenger[3] == 2.0
