from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityCandidate, OpportunityMechanism
from app.domain.trading import Side
from app.services.family_exit_landmark_extension import (
    CHAMPION_TARGET_R,
    HYPOTHESIS_ID,
    MAX_HOLDING_BARS,
    select_frozen_landmark_target,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 8, 1, 12, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD", bid=100.0, ask=100.2, tick_size=0.01,
        tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01,
        margin_required=10.0,
    )


def candidate(side: Side = Side.BUY) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=side,
        signal_at=START,
        entry_at=START,
        signal_index=3,
        entry_index=3,
        structural_stop=99.0 if side is Side.BUY else 101.0,
        target_r=1.5,
        max_holding_bars=12,
        reason="landmark extension unit test",
    )


def bar(at: datetime, *, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD", timeframe=Timeframe.M5, timestamp=at,
        open=close, high=high, low=low, close=close, volume=1,
    )


def test_landmark_extension_contract_is_preregistered() -> None:
    assert HYPOTHESIS_ID == "xau_sd_target_nearest_frozen_landmark_beyond_1_5r_v1"
    assert CHAMPION_TARGET_R == 1.5
    assert MAX_HOLDING_BARS == 12


def test_selects_nearest_side_aligned_frozen_landmark_beyond_champion_target(monkeypatch) -> None:
    import app.services.family_exit_landmark_extension as service

    c = candidate()
    bars = [bar(START - timedelta(minutes=20-i*5), high=100.8+i, low=99.0, close=100.0+i*0.1) for i in range(3)] + [bar(START, high=100.5, low=100.0, close=100.2)]
    monkeypatch.setattr(
        service,
        "frozen_landmarks_at_entry",
        lambda *_args, **_kwargs: {
            "previous_day_high": 103.2,
            "asia_high": 102.8,
            "london_high_so_far": 104.0,
        },
    )
    target = select_frozen_landmark_target(
        bars,
        c,
        spec(),
        slippage_spread_fraction=0.0,
    )
    # BUY entry = 100.4 with spread. Risk = 1.4, so 1.5R target = 102.5.
    assert target.landmark_type == "asia_high"
    assert target.target_price == 102.8
    assert target.target_r == pytest.approx((102.8 - 100.4) / 1.4)


def test_keeps_champion_when_no_frozen_landmark_is_beyond_target(monkeypatch) -> None:
    import app.services.family_exit_landmark_extension as service

    c = candidate()
    bars = [bar(START, high=100.5, low=100.0, close=100.2)] * 4
    monkeypatch.setattr(
        service,
        "frozen_landmarks_at_entry",
        lambda *_args, **_kwargs: {"asia_high": 102.0, "previous_day_high": 101.9},
    )
    target = select_frozen_landmark_target(
        bars,
        c,
        spec(),
        slippage_spread_fraction=0.0,
    )
    assert target.landmark_type is None
    assert target.target_r == CHAMPION_TARGET_R
