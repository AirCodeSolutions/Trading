from datetime import UTC, datetime, timedelta

from app.domain.broker import BrokerSymbolSpec, PositionSizeResult
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import (
    OpportunityBacktestConfig,
    OpportunityCandidate,
    OpportunityMechanism,
    ResearchSplit,
    TradeOutcome,
)
from app.domain.trading import Side
from app.services.trailing_research import _paper_trade_from_candidate

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_trailing_trade_sizing_uses_explicit_research_capital(monkeypatch) -> None:
    bars = [
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=START,
            open=4300.0,
            high=4302.0,
            low=4298.0,
            close=4301.0,
            volume=100,
        ),
        MarketBar(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=START + timedelta(minutes=5),
            open=4301.0,
            high=4304.0,
            low=4300.0,
            close=4303.0,
            volume=100,
        ),
    ]
    spec = BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4300.00,
        ask=4300.28,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10000.0,
        lot_step=0.01,
        margin_required=380.0,
    )
    config = OpportunityBacktestConfig(
        spec=spec,
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        split=ResearchSplit(
            train_end=START + timedelta(days=1),
            validation_end=START + timedelta(days=2),
        ),
        capital_eur=873863.20,
    )
    candidate = OpportunityCandidate(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=START,
        entry_at=START + timedelta(minutes=5),
        signal_index=0,
        entry_index=1,
        structural_stop=4295.0,
        target_r=1.0,
        max_holding_bars=12,
        reason="test",
    )
    baseline = TradeOutcome(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        side=Side.BUY,
        signal_at=START,
        entry_at=START + timedelta(minutes=5),
        exit_at=START + timedelta(minutes=10),
        lots=1.0,
        risk_eur=100.0,
        result_r=1.0,
        pnl_eur=100.0,
        execution_cost_r=0.1,
        exit_reason="target",
    )
    captured = {}

    def fake_size_position(request):
        captured["capital_eur"] = request.capital_eur
        return PositionSizeResult(
            approved=True,
            reason="approved",
            risk_fraction=0.01,
            risk_budget_eur=8738.632,
            stop_distance=6.35,
            spread=0.28,
            spread_to_stop=0.044,
            raw_lots=13.7,
            lots=13.7,
            expected_loss_eur=8700.0,
            min_lot_loss_eur=6.35,
            estimated_margin_eur=5206.0,
        )

    monkeypatch.setattr(
        "app.services.trailing_research.size_position",
        fake_size_position,
    )

    trade, rejection = _paper_trade_from_candidate(
        bars,
        candidate,
        config,
        baseline,
    )

    assert rejection is None
    assert trade is not None
    assert captured["capital_eur"] == 873863.20
