from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.broker import BrokerSymbolSpec
from app.domain.opportunity import (
    OpportunityBacktestResult,
    OpportunityMechanism,
    PerformanceSummary,
)
from app.domain.runtime_capital import (
    RuntimeCapitalSnapshot,
    RuntimeCapitalSource,
)
from app.services.execution_cost_stress import (
    SCENARIOS,
    build_xau_structural_displacement_cost_stress,
)

NOW = datetime(2026, 10, 1, 14, 0, tzinfo=ZoneInfo("Europe/Athens"))


def summary(*, trades: int, expectancy: float, pf: float, dd: float, cost: float) -> PerformanceSummary:
    return PerformanceSummary(
        trades=trades,
        total_r=expectancy * trades,
        expectancy_r=expectancy,
        profit_factor=pf,
        win_rate=0.5,
        max_drawdown_r=dd,
        total_pnl_eur=expectancy * trades * 100,
        average_execution_cost_r=cost,
    )


def result(*, val_exp: float, hold_exp: float) -> OpportunityBacktestResult:
    return OpportunityBacktestResult(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        candidates=100,
        executed=80,
        rejected=20,
        rejection_reasons={},
        train=summary(trades=40, expectancy=0.2, pf=1.5, dd=3, cost=0.05),
        validation=summary(
            trades=25,
            expectancy=val_exp,
            pf=2.0 if val_exp > 0 else 0.8,
            dd=2,
            cost=0.06,
        ),
        holdout=summary(
            trades=14,
            expectancy=hold_exp,
            pf=2.2 if hold_exp > 0 else 0.7,
            dd=2,
            cost=0.07,
        ),
        admission=AdmissionDecision(
            strategy_id="XAUUSD:structural_displacement_sequence",
            state=AdmissionState.SHADOW,
            reason="collect more evidence",
            weakest_expectancy_r=min(val_exp, hold_exp),
            worst_drawdown_r=2,
            paper_collection_candidate=True,
        ),
    )


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4160.0,
        ask=4160.2,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=10.0,
    )


def test_scenarios_are_preregistered_and_increasing() -> None:
    assert [
        (row.scenario.value, row.spread_multiplier, row.slippage_spread_fraction)
        for row in SCENARIOS
    ] == [
        ("observed", 1.0, 0.25),
        ("adverse_25", 1.25, 0.50),
        ("adverse_50", 1.50, 1.00),
    ]


def test_cost_stress_uses_demo_capital_and_changes_cost_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.execution_cost_stress.resolve_demo_sizing_capital",
        lambda files_dir: RuntimeCapitalSnapshot(
            capital_eur=123456.0,
            source=RuntimeCapitalSource.BROKER_EQUITY,
            is_demo=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.get_mt4_symbol_spec",
        lambda files_dir, symbol: spec(),
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.load_research_execution_model",
        lambda path: None,
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.resolve_mt4_history_path",
        lambda files_dir, symbol, timeframe: tmp_path / f"{timeframe.value}.csv",
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.read_mt4_csv",
        lambda path, symbol, timeframe: [object()],
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.load_macro_events",
        lambda path: [],
    )

    seen = []

    def fake_backtest(bars_m5, bars_m15, config):
        seen.append(
            (
                config.spec.spread,
                config.slippage_spread_fraction,
                config.capital_eur,
                config.requested_risk_fraction,
                config.mechanism,
            )
        )
        idx = len(seen) - 1
        return result(
            val_exp=(0.42, 0.40, 0.31)[idx],
            hold_exp=(0.66, 0.47, 0.46)[idx],
        )

    monkeypatch.setattr(
        "app.services.execution_cost_stress.run_opportunity_backtest",
        fake_backtest,
    )

    report = build_xau_structural_displacement_cost_stress(
        tmp_path,
        generated_at=NOW,
        risk_fraction=0.01,
        research_execution_model_path=tmp_path / "model.json",
        macro_events_path=tmp_path / "macro.json",
    )

    assert report.capital_eur == 123456.0
    assert report.capital_source == "broker_equity"
    assert report.target_r == 1.5
    assert report.authority_effect is False
    assert report.all_scenarios_positive_both_windows is True
    assert [round(row[0], 3) for row in seen] == [0.2, 0.25, 0.3]
    assert [row[1] for row in seen] == [0.25, 0.5, 1.0]
    assert all(row[2] == 123456.0 for row in seen)
    assert all(row[3] == 0.01 for row in seen)
    assert all(
        row[4] == OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE
        for row in seen
    )


def test_report_marks_failure_when_one_adverse_window_loses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.execution_cost_stress.resolve_demo_sizing_capital",
        lambda files_dir: RuntimeCapitalSnapshot(
            capital_eur=100000.0,
            source=RuntimeCapitalSource.BROKER_EQUITY,
            is_demo=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.get_mt4_symbol_spec",
        lambda files_dir, symbol: spec(),
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.load_research_execution_model",
        lambda path: None,
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.resolve_mt4_history_path",
        lambda files_dir, symbol, timeframe: tmp_path / f"{timeframe.value}.csv",
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.read_mt4_csv",
        lambda path, symbol, timeframe: [object()],
    )
    monkeypatch.setattr(
        "app.services.execution_cost_stress.load_macro_events",
        lambda path: [],
    )

    values = [(0.4, 0.5), (0.3, 0.2), (0.2, -0.1)]

    def fake_backtest(bars_m5, bars_m15, config):
        val_exp, hold_exp = values.pop(0)
        return result(val_exp=val_exp, hold_exp=hold_exp)

    monkeypatch.setattr(
        "app.services.execution_cost_stress.run_opportunity_backtest",
        fake_backtest,
    )

    report = build_xau_structural_displacement_cost_stress(
        tmp_path,
        generated_at=NOW,
        risk_fraction=0.01,
        research_execution_model_path=tmp_path / "model.json",
        macro_events_path=tmp_path / "macro.json",
    )

    assert report.all_scenarios_positive_both_windows is False
    assert report.scenarios[-1].positive_both_windows is False
    assert report.scenarios[-1].weakest_expectancy_r == -0.1


def test_unavailable_demo_capital_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.execution_cost_stress.resolve_demo_sizing_capital",
        lambda files_dir: RuntimeCapitalSnapshot(
            source=RuntimeCapitalSource.UNAVAILABLE,
            is_demo=True,
        ),
    )

    with pytest.raises(ValueError, match="capital is unavailable"):
        build_xau_structural_displacement_cost_stress(
            tmp_path,
            generated_at=NOW,
            risk_fraction=0.01,
            research_execution_model_path=tmp_path / "model.json",
            macro_events_path=tmp_path / "macro.json",
        )
