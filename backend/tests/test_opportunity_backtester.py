from datetime import UTC, datetime, timedelta

from app.domain.broker import BrokerSymbolSpec
from app.domain.macro import MacroEvent, MacroImpact
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityMechanism,
    ResearchSplit,
)
from app.services.opportunity_backtester import run_opportunity_backtest


def _m15_with_information_shock() -> list[MarketBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[MarketBar] = []
    for index in range(60):
        open_price = 100.0 + (0.03 if index % 2 else -0.03)
        close = 100.0 - (0.03 if index % 2 else -0.03)
        bars.append(
            MarketBar(
                symbol="TEST",
                timeframe=Timeframe.M15,
                timestamp=start + timedelta(minutes=15 * index),
                open=open_price,
                high=max(open_price, close) + 0.20,
                low=min(open_price, close) - 0.20,
                close=close,
                volume=100,
            )
        )

    shock_time = start + timedelta(minutes=15 * 60)
    bars.append(
        MarketBar(
            symbol="TEST",
            timeframe=Timeframe.M15,
            timestamp=shock_time,
            open=100.0,
            high=102.10,
            low=99.90,
            close=102.0,
            volume=500,
        )
    )
    return bars


def _m5_with_post_shock_confirmation() -> list[MarketBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[MarketBar] = []
    for index in range(183):
        bars.append(
            MarketBar(
                symbol="TEST",
                timeframe=Timeframe.M5,
                timestamp=start + timedelta(minutes=5 * index),
                open=100.0,
                high=100.12,
                low=99.88,
                close=100.0,
                volume=50,
            )
        )

    bars.append(
        MarketBar(
            symbol="TEST",
            timeframe=Timeframe.M5,
            timestamp=start + timedelta(minutes=5 * 183),
            open=102.0,
            high=102.20,
            low=101.95,
            close=102.15,
            volume=200,
        )
    )
    bars.append(
        MarketBar(
            symbol="TEST",
            timeframe=Timeframe.M5,
            timestamp=start + timedelta(minutes=5 * 184),
            open=102.15,
            high=103.10,
            low=102.10,
            close=103.0,
            volume=220,
        )
    )
    return bars


def _spec(tick_value: float = 1.0) -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="TEST",
        bid=102.15,
        ask=102.16,
        tick_size=0.01,
        tick_value=tick_value,
        min_lot=0.01,
        max_lot=10,
        lot_step=0.01,
        margin_required=100,
    )


def _config(tick_value: float = 1.0) -> OpportunityBacktestConfig:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return OpportunityBacktestConfig(
        spec=_spec(tick_value),
        mechanism=OpportunityMechanism.POST_SHOCK_CONTINUATION,
        split=ResearchSplit(
            train_end=start + timedelta(hours=10),
            validation_end=start + timedelta(hours=14),
        ),
    )


def test_post_shock_backtest_enters_next_bar_and_reaches_target() -> None:
    result = run_opportunity_backtest(
        _m5_with_post_shock_confirmation(),
        _m15_with_information_shock(),
        _config(),
    )

    assert result.candidates == 1
    assert result.executed == 1
    assert result.holdout.trades == 1
    assert result.holdout.total_r == 1.8
    assert result.holdout.total_pnl_eur > 0
    assert result.admission.state == "shadow"


def test_candidate_is_rejected_when_minimum_lot_breaks_200_eur_risk_budget() -> None:
    result = run_opportunity_backtest(
        _m5_with_post_shock_confirmation(),
        _m15_with_information_shock(),
        _config(tick_value=100.0),
    )

    assert result.candidates == 1
    assert result.executed == 0
    assert result.rejected == 1
    assert result.rejection_reasons == {
        "minimum broker lot exceeds the risk budget": 1
    }



def test_candidate_is_rejected_inside_shared_macro_blackout() -> None:
    config = _config().model_copy(
        update={
            "macro_events": [
                MacroEvent(
                    event_id="test-fomc",
                    name="FOMC decision-day safety window",
                    start_at=datetime(2026, 1, 1, 15, 0, tzinfo=UTC),
                    end_at=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
                    impact=MacroImpact.HIGH,
                    currencies=["USD"],
                    pre_block_minutes=0,
                    post_block_minutes=0,
                    source="test",
                )
            ]
        }
    )

    result = run_opportunity_backtest(
        _m5_with_post_shock_confirmation(),
        _m15_with_information_shock(),
        config,
    )

    assert result.candidates == 1
    assert result.executed == 0
    assert result.rejected == 1
    assert result.rejection_reasons == {"macro_blackout": 1}


def test_candidate_outside_macro_blackout_keeps_original_outcome() -> None:
    config = _config().model_copy(
        update={
            "macro_events": [
                MacroEvent(
                    event_id="past-cpi",
                    name="CPI",
                    start_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                    end_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                    impact=MacroImpact.HIGH,
                    currencies=["USD"],
                    pre_block_minutes=30,
                    post_block_minutes=45,
                    source="test",
                )
            ]
        }
    )

    result = run_opportunity_backtest(
        _m5_with_post_shock_confirmation(),
        _m15_with_information_shock(),
        config,
    )

    assert result.executed == 1
    assert result.rejection_reasons == {}



def test_holdout_end_excludes_bars_that_close_after_cutover() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    config = _config().model_copy(
        update={
            "split": ResearchSplit(
                train_end=start + timedelta(hours=10),
                validation_end=start + timedelta(hours=14),
                holdout_end=start + timedelta(hours=15, minutes=18),
            )
        }
    )

    result = run_opportunity_backtest(
        _m5_with_post_shock_confirmation(),
        _m15_with_information_shock(),
        config,
    )

    assert result.candidates == 0
    assert result.executed == 0
    assert result.holdout.trades == 0
