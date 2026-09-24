from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.trading import Side
from app.domain.xau_feasible_pullback_shadow import FeasiblePullbackStatus
from app.services.xau_feasible_pullback_shadow import (
    advance_xau_feasible_pullback_shadow_once,
    create_xau_feasible_pullback_probe,
    resolve_xau_feasible_pullback_probe,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 24, 10, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4280.0,
        ask=4280.28,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=376.0,
    )


def diagnostic(
    *,
    side: Side = Side.BUY,
    reason: str = "minimum broker lot exceeds the risk budget",
) -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.ASIA_RANGE_SWEEP_REVERSAL,
        evaluated_at=NOW,
        latest_closed_m5_at=NOW - timedelta(minutes=5),
        latest_closed_m15_at=NOW - timedelta(minutes=15),
        state=ShadowSignalState.SIGNAL_BLOCKED,
        side=side,
        regime=MarketRegime.BALANCED,
        regime_direction=0,
        atr_m15=6.0,
        atr_ratio=1.0,
        volatility_percentile=0.5,
        efficiency=0.4,
        structural_stop=4274.0 if side == Side.BUY else 4286.0,
        target_r=1.5,
        max_holding_bars=12,
        base_risk=ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=False,
            reason=reason,
            lots=0,
            expected_loss_eur=0,
            spread_to_stop=0.05,
        ),
        max_risk=ShadowSizingSnapshot(
            risk_fraction=0.02,
            approved=True,
            reason="risk and execution constraints satisfied",
            lots=0.01,
            expected_loss_eur=6.0,
            spread_to_stop=0.05,
        ),
        reason="test signal",
    )


def bar(
    index: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=NOW + timedelta(minutes=5 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def test_probe_uses_exact_base_risk_budget(monkeypatch) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)

    probe = create_xau_feasible_pullback_probe(
        diagnostic(),
        spec(),
        signal_at=NOW,
    )

    assert probe is not None
    assert probe.limit_entry == 4278.0
    assert probe.stop_price == 4274.0
    assert probe.risk_eur == 4.0
    assert probe.target_price == 4284.0


def test_probe_requires_min_lot_block_reason(monkeypatch) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)

    probe = create_xau_feasible_pullback_probe(
        diagnostic(reason="spread consumes too much of the stop distance"),
        spec(),
        signal_at=NOW,
    )

    assert probe is None


def test_pending_probe_fills_then_hits_target(monkeypatch) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    probe = create_xau_feasible_pullback_probe(
        diagnostic(),
        spec(),
        signal_at=NOW,
    )
    assert probe is not None

    bars = [
        bar(0, open_=4280.0, high=4280.4, low=4277.5, close=4278.2),
        bar(1, open_=4278.2, high=4284.5, low=4277.9, close=4284.2),
    ]

    resolved = resolve_xau_feasible_pullback_probe(probe, bars)

    assert resolved.status == FeasiblePullbackStatus.TARGET
    assert resolved.fill_at == NOW
    assert resolved.result_r == 1.5


def test_pending_probe_resolves_no_fill_after_three_bars(monkeypatch) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    probe = create_xau_feasible_pullback_probe(
        diagnostic(),
        spec(),
        signal_at=NOW,
    )
    assert probe is not None

    bars = [
        bar(i, open_=4281.0, high=4282.0, low=4279.0, close=4281.0)
        for i in range(3)
    ]

    resolved = resolve_xau_feasible_pullback_probe(probe, bars)

    assert resolved.status == FeasiblePullbackStatus.NO_FILL
    assert resolved.result_r is None


def test_shadow_collection_starts_without_backfill(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_dir = tmp_path / "files"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    monkeypatch.setattr(
        "app.services.xau_feasible_pullback_shadow.get_mt4_symbol_spec",
        lambda *args, **kwargs: spec(),
    )
    monkeypatch.setattr(
        "app.services.xau_feasible_pullback_shadow.load_closed_market_bars",
        lambda *args, **kwargs: [],
    )

    summary = advance_xau_feasible_pullback_shadow_once(
        files_dir,
        runtime_dir,
        diagnostic(),
        NOW,
    )

    assert summary.started_at == NOW
    assert summary.resolved == 0
    assert summary.open_probe is None
