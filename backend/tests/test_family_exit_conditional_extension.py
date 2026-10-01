from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.trading import Side
from app.services.family_exit_conditional_extension import (
    CHALLENGER_TARGET_R,
    CHAMPION_TARGET_R,
    HYPOTHESIS_ID,
    STRUCTURE_WINDOW,
    simulate_conditional_extension,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 8, 1, 12, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD", bid=100.0, ask=100.2, tick_size=0.01,
        tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01,
        margin_required=10.0,
    )


def candidate() -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=START,
        entry_at=START,
        signal_index=0,
        entry_index=0,
        structural_stop=99.0,
        target_r=1.5,
        max_holding_bars=12,
        reason="conditional extension unit test",
    )


def bar(index: int, *, close: float, high: float | None = None, low: float = 100.0) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * index),
        open=100.2,
        high=high if high is not None else max(100.3, close),
        low=low,
        close=close,
        volume=1,
    )


def test_contract_is_preregistered_and_single_axis() -> None:
    assert HYPOTHESIS_ID == "xau_sd_extend_2r_if_prior_3_m5_directional_v1"
    assert CHAMPION_TARGET_R == 1.5
    assert CHALLENGER_TARGET_R == 2.0
    assert STRUCTURE_WINDOW == 3


def test_extends_only_when_three_prior_closed_m5_are_directional() -> None:
    bars = [
        bar(0, close=100.5),
        bar(1, close=100.8),
        bar(2, close=101.1),
        bar(3, close=101.4, high=103.3),
    ]
    outcome, qualified = simulate_conditional_extension(
        bars,
        candidate(),
        spec(),
        capital_eur=100000.0,
        requested_risk_fraction=0.01,
        slippage_spread_fraction=0.0,
    )
    assert qualified is True
    assert outcome.exit_reason == "extended_target"
    assert outcome.result_r == 2.0


def test_keeps_1_5r_when_prior_closes_are_not_directional() -> None:
    bars = [
        bar(0, close=100.8),
        bar(1, close=100.6),
        bar(2, close=101.1),
        bar(3, close=101.3, high=102.7),
    ]
    outcome, qualified = simulate_conditional_extension(
        bars,
        candidate(),
        spec(),
        capital_eur=100000.0,
        requested_risk_fraction=0.01,
        slippage_spread_fraction=0.0,
    )
    assert qualified is False
    assert outcome.exit_reason == "target"
    assert outcome.result_r == 1.5
