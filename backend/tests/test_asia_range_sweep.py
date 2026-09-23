from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.macro import MacroEvent, MacroImpact
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityBacktestConfig, OpportunityMechanism, ResearchSplit
from app.domain.trading import Side
from app.services.blocked_probe_registry import _parse_state_name as parse_probe_state
from app.services.multi_shadow_collector import shadow_mechanism_enabled
from app.services.opportunity_backtester import run_opportunity_backtest
from app.services.opportunity_strategies import (
    _asia_range_sweep_candidate,
    _asia_range_sweep_signal,
)
from app.services.paper_registry import _parse_state_name as parse_paper_state

TZ = ZoneInfo("Europe/Athens")
DAY = datetime(2026, 6, 15, tzinfo=TZ)


def _bar(at: datetime, *, open_: float, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        symbol="GBPUSD",
        timeframe=Timeframe.M5,
        timestamp=at,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def _setup() -> list[MarketBar]:
    bars = []
    start = DAY.replace(hour=2)
    for index in range(96):
        bars.append(
            _bar(
                start + timedelta(minutes=5 * index),
                open_=1.3000,
                high=1.3010,
                low=1.2990,
                close=1.3000,
            )
        )
    bars.append(
        _bar(
            DAY.replace(hour=10),
            open_=1.3010,
            high=1.3025,
            low=1.2995,
            close=1.3000,
        )
    )
    bars.append(
        _bar(
            DAY.replace(hour=10, minute=5),
            open_=1.3000,
            high=1.3004,
            low=1.2995,
            close=1.2998,
        )
    )
    return bars


def _m15() -> list[MarketBar]:
    start = DAY - timedelta(hours=13)
    return [
        MarketBar(
            symbol="GBPUSD",
            timeframe=Timeframe.M15,
            timestamp=start + timedelta(minutes=15 * index),
            open=1.3000,
            high=1.3010,
            low=1.2990,
            close=1.3000,
            volume=100,
        )
        for index in range(60)
    ]


def _spec(spread: float = 0.00011) -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="GBPUSD",
        bid=1.3000,
        ask=1.3000 + spread,
        tick_size=0.00001,
        tick_value=0.5,
        min_lot=0.01,
        max_lot=10.0,
        lot_step=0.01,
        margin_required=100.0,
    )


def _config(
    *, spread: float = 0.00011, macro_events: list[MacroEvent] | None = None
) -> OpportunityBacktestConfig:
    return OpportunityBacktestConfig(
        spec=_spec(spread),
        mechanism=OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        split=ResearchSplit(
            train_end=DAY + timedelta(days=1),
            validation_end=DAY + timedelta(days=2),
        ),
        macro_events=macro_events or [],
    )


def test_asia_range_sweep_uses_completed_0200_1000_range_and_next_bar_entry() -> None:
    bars = _setup()
    atr = [0.0020] * len(bars)

    candidate = _asia_range_sweep_candidate(bars, atr, 96)

    assert candidate is not None
    assert candidate.side == Side.SELL
    assert candidate.signal_index == 96
    assert candidate.entry_index == 97
    assert candidate.entry_at == bars[97].timestamp
    assert candidate.structural_stop == 1.3028
    assert candidate.target_r == 1.5
    assert candidate.max_holding_bars == 12


def test_asia_range_sweep_runtime_and_backtest_geometry_are_identical() -> None:
    bars = _setup()
    atr = [0.0020] * len(bars)
    candidate = _asia_range_sweep_candidate(bars, atr, 96)
    signal = _asia_range_sweep_signal(bars[:97], atr[:97])

    assert candidate is not None
    assert signal is not None
    assert signal[0] == candidate.side
    assert signal[1] == candidate.structural_stop
    assert signal[2] == candidate.target_r
    assert signal[3] == candidate.max_holding_bars


def test_asia_range_sweep_does_not_use_future_bars() -> None:
    bars = _setup()
    atr = [0.0020] * len(bars)
    first = _asia_range_sweep_candidate(bars, atr, 96)
    bars.append(
        _bar(
            DAY.replace(hour=10, minute=10),
            open_=2.0,
            high=3.0,
            low=0.5,
            close=2.5,
        )
    )
    second = _asia_range_sweep_candidate(bars, atr + [0.5], 96)

    assert first is not None and second is not None
    assert second.structural_stop == first.structural_stop
    assert second.side == first.side


def test_asia_range_sweep_requires_complete_asia_window_and_london_observation() -> None:
    bars = _setup()
    atr = [0.0020] * len(bars)
    incomplete = bars[37:97]  # 59 Asia bars + the 10:00 signal bar

    assert _asia_range_sweep_signal(incomplete, atr[: len(incomplete)]) is None

    late = bars[:96] + [
        _bar(
            DAY.replace(hour=13),
            open_=1.3010,
            high=1.3025,
            low=1.2995,
            close=1.3000,
        )
    ]
    assert _asia_range_sweep_signal(late, [0.0020] * len(late)) is None


def test_asia_range_sweep_uses_only_first_qualifying_london_sweep() -> None:
    bars = _setup()
    bars.append(
        _bar(
            DAY.replace(hour=10, minute=10),
            open_=1.3010,
            high=1.3026,
            low=1.2995,
            close=1.3000,
        )
    )

    assert _asia_range_sweep_signal(bars, [0.0020] * len(bars)) is None


def test_asia_range_sweep_runtime_scope_is_gbpusd_and_xauusd() -> None:
    mechanism = OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL
    assert shadow_mechanism_enabled("GBPUSD", mechanism) is True
    assert shadow_mechanism_enabled("XAUUSD", mechanism) is True
    assert shadow_mechanism_enabled("EURUSD", mechanism) is False
    assert shadow_mechanism_enabled("BTCUSD", mechanism) is False
    assert shadow_mechanism_enabled("XAGUSD", mechanism) is False


def test_asia_range_sweep_registry_parsing() -> None:
    expected_gbp = (
        "GBPUSD",
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        "GBPUSD_asia_range_sweep",
    )
    expected_xau = (
        "XAUUSD",
        OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        "XAUUSD_asia_range_sweep",
    )
    assert parse_paper_state(Path("GBPUSD_asia_range_sweep_paper_state.json")) == expected_gbp
    assert parse_probe_state(Path("GBPUSD_asia_range_sweep_blocked_probe_state.json")) == expected_gbp
    assert parse_paper_state(Path("XAUUSD_asia_range_sweep_paper_state.json")) == expected_xau
    assert parse_probe_state(Path("XAUUSD_asia_range_sweep_blocked_probe_state.json")) == expected_xau


def test_asia_range_sweep_keeps_macro_blackout_gate() -> None:
    event = MacroEvent(
        event_id="test-usd",
        name="USD high impact",
        start_at=DAY.replace(hour=10),
        end_at=DAY.replace(hour=10, minute=30),
        impact=MacroImpact.HIGH,
        currencies=["USD"],
        pre_block_minutes=0,
        post_block_minutes=0,
        source="test",
    )
    result = run_opportunity_backtest(_setup(), _m15(), _config(macro_events=[event]))

    assert result.candidates == 1
    assert result.executed == 0
    assert result.rejection_reasons == {"macro_blackout": 1}


def test_asia_range_sweep_keeps_spread_stop_gate() -> None:
    result = run_opportunity_backtest(_setup(), _m15(), _config(spread=0.0010))

    assert result.candidates == 1
    assert result.executed == 0
    assert result.rejection_reasons == {"spread consumes too much of the stop distance": 1}
