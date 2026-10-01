from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.domain.admission import AdmissionState
from app.domain.broker import BrokerSymbolSpec
from app.domain.execution_cost_stress import (
    ExecutionCostStressReport,
    ExecutionCostStressRow,
)
from app.domain.opportunity import (
    OpportunityMechanism,
    PerformanceSummary,
)
from app.services.execution_cost_stress import (
    SCENARIOS,
    _edge_survives,
    _stressed_spec,
    load_execution_cost_stress_report,
    save_execution_cost_stress_report,
)
from app.services.probe_review import default_probe_review_split

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=ZoneInfo("Europe/Athens"))


def summary(
    *,
    expectancy: float,
    profit_factor: float,
    drawdown: float,
) -> PerformanceSummary:
    return PerformanceSummary(
        trades=20,
        total_r=expectancy * 20,
        expectancy_r=expectancy,
        profit_factor=profit_factor,
        win_rate=0.5,
        max_drawdown_r=drawdown,
        total_pnl_eur=100,
        average_execution_cost_r=0.1,
    )
def test_scenarios_are_preregistered_and_monotonic() -> None:
    assert [item.scenario_id for item in SCENARIOS] == [
        "observed",
        "spread_1_25x",
        "spread_1_50x",
    ]
    assert [item.spread_multiplier for item in SCENARIOS] == [1.0, 1.25, 1.5]
    assert all(item.slippage_spread_fraction == 0.25 for item in SCENARIOS)


def test_stressed_spec_changes_only_effective_spread() -> None:
    spec = BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=100.0,
        ask=100.4,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100,
        lot_step=0.01,
        margin_required=10,
    )
    stressed = _stressed_spec(spec, 0.4, 1.5)

    assert stressed.bid == spec.bid
    assert stressed.ask == 100.6
    assert stressed.spread == pytest.approx(0.6)
    assert stressed.tick_size == spec.tick_size
    assert stressed.tick_value == spec.tick_value
    assert stressed.min_lot == spec.min_lot
    assert stressed.max_lot == spec.max_lot
    assert stressed.lot_step == spec.lot_step
    assert stressed.margin_required == spec.margin_required
def test_edge_survival_reuses_existing_expectancy_pf_and_dd_floors() -> None:
    good = SimpleNamespace(
        validation=summary(expectancy=0.1, profit_factor=1.05, drawdown=12.0),
        holdout=summary(expectancy=0.2, profit_factor=1.2, drawdown=5.0),
    )
    assert _edge_survives(good) is True

    for bad in [
        SimpleNamespace(
            validation=summary(expectancy=0.0, profit_factor=2, drawdown=1),
            holdout=summary(expectancy=0.2, profit_factor=2, drawdown=1),
        ),
        SimpleNamespace(
            validation=summary(expectancy=0.1, profit_factor=1.049, drawdown=1),
            holdout=summary(expectancy=0.2, profit_factor=2, drawdown=1),
        ),
        SimpleNamespace(
            validation=summary(expectancy=0.1, profit_factor=2, drawdown=12.001),
            holdout=summary(expectancy=0.2, profit_factor=2, drawdown=1),
        ),
    ]:
        assert _edge_survives(bad) is False
def test_report_roundtrip_is_atomic_and_research_only(tmp_path) -> None:
    validation = summary(expectancy=0.2, profit_factor=1.5, drawdown=2)
    holdout = summary(expectancy=0.3, profit_factor=1.7, drawdown=3)
    report = ExecutionCostStressReport(
        generated_at=NOW,
        capital_eur=100_000,
        capital_source="broker_equity",
        split=default_probe_review_split(),
        rows=[
            ExecutionCostStressRow(
                strategy_id="XAUUSD:structural_displacement_sequence",
                symbol="XAUUSD",
                mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
                scenario=SCENARIOS[0],
                validation=validation,
                holdout=holdout,
                admission_state=AdmissionState.SHADOW,
                edge_survives=True,
            )
        ],
        broker_authority=False,
    )
    path = tmp_path / "execution_cost_stress.json"
    save_execution_cost_stress_report(path, report)
    loaded = load_execution_cost_stress_report(path)

    assert loaded == report
    assert loaded is not None
    assert loaded.broker_authority is False
    assert not path.with_suffix(".json.tmp").exists()
