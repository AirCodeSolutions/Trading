from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism, TradeOutcome
from app.domain.runtime_capital import RuntimeCapitalSnapshot, RuntimeCapitalSource
from app.domain.trading import Side
from app.domain.trading_intelligence import (
    OpportunityCausalContext,
    OpportunityCausalPattern,
)
from app.services.xau_auction_precursor_shadow import (
    LEDGER_FILE,
    advance_xau_auction_precursor_shadow_once,
    load_xau_auction_precursor_shadow_summary,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 24, 18, 0, tzinfo=TZ)


def _bars(count: int = 40) -> list[MarketBar]:
    rows = []
    price = 4300.0
    start = NOW - timedelta(minutes=5 * 30)
    for index in range(count):
        at = start + timedelta(minutes=5 * index)
        rows.append(
            MarketBar(
                symbol="XAUUSD",
                timeframe=Timeframe.M5,
                timestamp=at,
                open=price,
                high=price + 2.0,
                low=price - 2.0,
                close=price + 0.5,
                volume=100,
            )
        )
        price += 0.5
    return rows


def _precursor(bars: list[MarketBar]) -> CausalPrecursorObservation:
    latest = bars[10]
    return CausalPrecursorObservation(
        symbol="XAUUSD",
        first_seen_at=latest.timestamp + timedelta(minutes=5),
        latest_closed_m5_at=latest.timestamp,
        pattern=OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM,
        side=Side.BUY,
        context=OpportunityCausalContext(
            pattern=OpportunityCausalPattern.AUCTION_FAILURE_RECLAIM,
            side=Side.BUY,
        ),
    )


def _spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4300.0,
        ask=4300.28,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=380.0,
    )


def test_shadow_starts_fresh_without_backfill(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.load_causal_precursors",
        lambda *args, **kwargs: [_precursor(_bars())],
    )

    summary = advance_xau_auction_precursor_shadow_once(
        tmp_path,
        tmp_path,
        NOW,
    )

    assert summary.started_at == NOW
    assert summary.resolved == 0
    assert not (tmp_path / LEDGER_FILE).exists()


def test_future_precursor_is_resolved_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bars = _bars()
    advance_xau_auction_precursor_shadow_once(
        tmp_path,
        tmp_path,
        NOW,
    )
    precursor = _precursor(bars).model_copy(
        update={"first_seen_at": NOW + timedelta(minutes=5)}
    )

    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.load_causal_precursors",
        lambda *args, **kwargs: [precursor],
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.load_recent_closed_market_bars",
        lambda *args, **kwargs: bars,
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.resolve_demo_sizing_capital",
        lambda *args, **kwargs: RuntimeCapitalSnapshot(
            capital_eur=875000.0,
            source=RuntimeCapitalSource.BROKER_EQUITY,
            is_demo=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.get_mt4_symbol_spec",
        lambda *args, **kwargs: _spec(),
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.load_research_execution_model",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.apply_research_execution_model",
        lambda spec, model: spec,
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.load_macro_events",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow.active_macro_blackouts",
        lambda *args, **kwargs: [],
    )

    outcome = TradeOutcome(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_TRANSITION,
        side=Side.BUY,
        signal_at=precursor.first_seen_at,
        entry_at=precursor.first_seen_at,
        exit_at=precursor.first_seen_at + timedelta(minutes=20),
        lots=5.0,
        risk_eur=750.0,
        result_r=1.0,
        pnl_eur=750.0,
        execution_cost_r=0.05,
        exit_reason="target",
    )
    monkeypatch.setattr(
        "app.services.xau_auction_precursor_shadow._simulate_candidate",
        lambda *args, **kwargs: (outcome, 20, None),
    )

    first = advance_xau_auction_precursor_shadow_once(
        tmp_path,
        tmp_path,
        NOW + timedelta(hours=3),
    )
    second = advance_xau_auction_precursor_shadow_once(
        tmp_path,
        tmp_path,
        NOW + timedelta(hours=3, minutes=5),
    )

    assert first.resolved == 1
    assert first.wins == 1
    assert first.expectancy_r == 1.0
    assert first.profit_factor == 99.0
    assert second.resolved == 1
    assert len(load_xau_auction_precursor_shadow_summary(tmp_path).recent) == 1
