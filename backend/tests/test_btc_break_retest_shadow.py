from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.regime import MarketRegime, RegimeSnapshot
from app.domain.shadow import ShadowSignalState
from app.domain.trading import Side
from app.services.btc_break_retest_shadow import (
    _latest_break_retest_signal,
    scan_btc_break_retest_shadow,
)
from app.services.opportunity_strategies import _atr_series

TZ = ZoneInfo("Europe/Athens")


def make_m5_signal_bars() -> list[MarketBar]:
    start = datetime(2026, 9, 19, 12, 30, tzinfo=TZ)
    bars: list[MarketBar] = []
    for index in range(30):
        open_price = 100.0
        high = 100.20
        low = 99.80
        close = 100.0
        if index == 26:
            close = 100.55
            high = 100.65
        elif index == 27:
            open_price = 100.50
            close = 100.60
            high = 100.70
            low = 100.35
        elif index == 28:
            open_price = 100.55
            close = 100.45
            high = 100.65
            low = 100.35
        elif index == 29:
            open_price = 100.30
            high = 100.85
            low = 100.15
            close = 100.75
        bars.append(
            MarketBar(
                symbol="BTCUSD",
                timeframe=Timeframe.M5,
                timestamp=start + timedelta(minutes=5 * index),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=100,
            )
        )
    return bars


def make_directional_m15_bars() -> list[MarketBar]:
    start = datetime(2026, 9, 18, 22, 0, tzinfo=TZ)
    bars: list[MarketBar] = []
    price = 95.0
    for index in range(60):
        close = price + 0.20
        bars.append(
            MarketBar(
                symbol="BTCUSD",
                timeframe=Timeframe.M15,
                timestamp=start + timedelta(minutes=15 * index),
                open=price,
                high=close + 0.10,
                low=price - 0.10,
                close=close,
                volume=300,
            )
        )
        price = close
    return bars


def btc_spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="BTCUSD",
        bid=100.74,
        ask=100.75,
        tick_size=0.01,
        tick_value=0.10,
        min_lot=0.01,
        max_lot=10,
        lot_step=0.01,
        margin_required=10,
    )


def test_latest_break_retest_signal_matches_backtest_geometry() -> None:
    bars = make_m5_signal_bars()
    regime = RegimeSnapshot(
        symbol="BTCUSD",
        at=bars[-1].timestamp,
        regime=MarketRegime.DIRECTIONAL,
        direction=1,
        confidence=0.8,
        atr=1.0,
        atr_ratio=1.2,
        efficiency=0.7,
        shock_ratio=1.0,
        reason="test",
    )

    signal = _latest_break_retest_signal(bars, _atr_series(bars), regime)

    assert signal is not None
    assert signal[0] == Side.BUY
    assert signal[2] > 0
    assert signal[4] > 0


def test_shadow_scanner_never_creates_execution_proposal() -> None:
    m5 = make_m5_signal_bars()
    m15 = make_directional_m15_bars()
    evaluated_at = m5[-1].timestamp + timedelta(minutes=5)

    result = scan_btc_break_retest_shadow(
        m5,
        m15,
        btc_spec(),
        evaluated_at,
    )

    assert result.mechanism == "break_retest_reaccel"
    assert result.state in {
        ShadowSignalState.SIGNAL_EXECUTABLE,
        ShadowSignalState.SIGNAL_BLOCKED,
        ShadowSignalState.NO_SIGNAL,
    }
    assert not hasattr(result, "proposal_id")


def test_shadow_scanner_rejects_stale_snapshot() -> None:
    m5 = make_m5_signal_bars()
    m15 = make_directional_m15_bars()
    evaluated_at = m5[-1].timestamp + timedelta(minutes=30)

    result = scan_btc_break_retest_shadow(
        m5,
        m15,
        btc_spec(),
        evaluated_at,
    )

    assert result.state == ShadowSignalState.NO_SIGNAL
    assert "stale" in result.reason
