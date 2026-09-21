from datetime import UTC, datetime
from pathlib import Path

from app.domain.admission import AdmissionDecision, AdmissionState
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestResult,
    OpportunityMechanism,
    PerformanceSummary,
    PortfolioResearchRequest,
    ResearchSplit,
)
from app.services import opportunity_matrix
from app.services.research_broker_specs import load_research_broker_specs


def summary() -> PerformanceSummary:
    return PerformanceSummary(
        trades=0,
        total_r=0,
        expectancy_r=0,
        profit_factor=0,
        win_rate=0,
        max_drawdown_r=0,
        total_pnl_eur=0,
        average_execution_cost_r=0,
    )


def result(symbol: str, mechanism: OpportunityMechanism) -> OpportunityBacktestResult:
    return OpportunityBacktestResult(
        symbol=symbol,
        mechanism=mechanism,
        candidates=0,
        executed=0,
        rejected=0,
        rejection_reasons={},
        train=summary(),
        validation=summary(),
        holdout=summary(),
        admission=AdmissionDecision(
            strategy_id=f"{symbol}:{mechanism.value}",
            state=AdmissionState.SHADOW,
            reason="test",
            weakest_expectancy_r=0,
            worst_drawdown_r=0,
        ),
    )


def test_research_spec_profile_is_versioned_and_loadable(tmp_path: Path) -> None:
    path = tmp_path / "research_specs.json"
    path.write_text(
        """
        {
          "specs": [
            {
              "symbol": "GBPUSD",
              "bid": 1.30000,
              "ask": 1.30011,
              "tick_size": 0.00001,
              "tick_value": 0.87,
              "min_lot": 0.01,
              "max_lot": 10000,
              "lot_step": 0.01,
              "margin_required": 116.5
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    specs = load_research_broker_specs(path)

    assert specs["GBPUSD"].spread == 0.00011


def test_portfolio_research_uses_frozen_spec_not_live_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile = tmp_path / "research_specs.json"
    profile.write_text(
        """
        {
          "specs": [
            {
              "symbol": "GBPUSD",
              "bid": 1.30000,
              "ask": 1.30011,
              "tick_size": 0.00001,
              "tick_value": 0.87,
              "min_lot": 0.01,
              "max_lot": 10000,
              "lot_step": 0.01,
              "margin_required": 116.5
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    m5_path = tmp_path / "GBPUSD-M5.csv"
    m15_path = tmp_path / "GBPUSD-M15.csv"
    m5_path.write_text("placeholder", encoding="utf-8")
    m15_path.write_text("placeholder", encoding="utf-8")

    bar_m5 = MarketBar(
        symbol="GBPUSD",
        timeframe=Timeframe.M5,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=1.3,
        high=1.31,
        low=1.29,
        close=1.3,
        volume=1,
    )
    bar_m15 = bar_m5.model_copy(update={"timeframe": Timeframe.M15})
    captured = {}

    monkeypatch.setattr(
        opportunity_matrix,
        "list_mt4_symbol_specs",
        lambda *_: (_ for _ in ()).throw(AssertionError("live specs must not be used")),
    )
    monkeypatch.setattr(
        opportunity_matrix,
        "resolve_mt4_history_path",
        lambda _files, _symbol, timeframe: (
            m5_path if timeframe == Timeframe.M5 else m15_path
        ),
    )
    monkeypatch.setattr(
        opportunity_matrix,
        "read_mt4_csv",
        lambda _path, _symbol, timeframe: (
            [bar_m5] if timeframe == Timeframe.M5 else [bar_m15]
        ),
    )

    def fake_backtest(_m5, _m15, config):
        captured["spread"] = config.spec.spread
        return result(config.spec.symbol, config.mechanism)

    monkeypatch.setattr(
        opportunity_matrix,
        "run_opportunity_backtest",
        fake_backtest,
    )

    request = PortfolioResearchRequest(
        split=ResearchSplit(
            train_end=datetime(2026, 7, 1, tzinfo=UTC),
            validation_end=datetime(2026, 9, 1, tzinfo=UTC),
            holdout_end=datetime(2026, 9, 20, tzinfo=UTC),
        ),
        symbols=["GBPUSD"],
        mechanisms=[OpportunityMechanism.FAILED_AUCTION_REVERSAL],
    )

    opportunity_matrix.run_mt4_portfolio_research(
        tmp_path,
        request,
        research_broker_specs_path=profile,
    )

    assert captured["spread"] == 0.00011
