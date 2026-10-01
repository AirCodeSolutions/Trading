from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.demo_execution import DemoBridgePosition
from app.domain.opportunity import OpportunityMechanism
from app.domain.portfolio import (
    BrokerDemoSnapshot,
    PaperStrategyRuntime,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    ProspectiveQualification,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.domain.portfolio_allocator import AllocationDecision
from app.domain.shadow_paper import ShadowPaperSummary, ShadowPaperTrade
from app.domain.trading import Side
from app.services.portfolio_allocator import build_portfolio_opportunity_allocation

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=ZoneInfo("Europe/Athens"))
def spec(symbol: str) -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol=symbol,
        bid=100,
        ask=101,
        tick_size=1,
        tick_value=1,
        min_lot=0.01,
        max_lot=100,
        lot_step=0.01,
        margin_required=1,
    )


def strategy(
    symbol: str,
    mechanism: OpportunityMechanism,
    risk: float,
    *,
    lots: float = 1.0,
    allowed: bool = True,
) -> PaperStrategyRuntime:
    strategy_id = f"{symbol}:{mechanism.value}"
    trade = ShadowPaperTrade(
        trade_id=strategy_id,
        symbol=symbol,
        mechanism=mechanism,
        side=Side.BUY,
        signal_at=NOW,
        entry_bar_at=NOW,
        opened_at=NOW,
        entry_price=100,
        stop_price=90,
        target_price=118,
        spread_at_entry=1,
        lots=lots,
        risk_eur=risk,
        risk_distance=10,
        target_r=1.8,
        max_holding_bars=18,
    )
    summary = ShadowPaperSummary(
        closed_trades=5,
        wins=3,
        losses=2,
        total_r=1,
        expectancy_r=0.2,
        profit_factor=1.5,
        max_drawdown_r=2,
        total_pnl_eur=100,
        open_trade=trade,
    )
    qualification = ProspectiveQualification(
        strategy_id=strategy_id,
        state=ProspectiveQualificationState.COLLECTING,
        closed_trades=5,
        expectancy_r=0.2,
        profit_factor=1.5,
        max_drawdown_r=2,
        reason="test",
    )
    return PaperStrategyRuntime(
        strategy_id=strategy_id,
        symbol=symbol,
        mechanism=mechanism,
        summary=summary,
        qualification=qualification,
        historical_weakest_expectancy_r=0.1,
        paper_entry_allowed=allowed,
    )


def overview(
    rows: list[PaperStrategyRuntime],
    *,
    equity: float = 10_000,
    balance: float = 10_000,
    selected: str | None = None,
) -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=balance,
            equity=equity,
            margin=0,
            free_margin=max(equity, balance),
            observed_positions=0,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=max(equity, balance, 1),
            reference_capital_source="broker_equity",
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=sum(
                row.summary.open_trade.risk_eur
                for row in rows
                if row.summary.open_trade is not None
            ),
            research_paper_open_positions=len(rows),
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=1,
            remaining_daily_loss_budget_eur=0,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.DEMO_COLLECTION,
            selected_strategy_id=selected,
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[row.qualification for row in rows],
        paper_strategies=rows,
    )
def bridge(symbol: str, *, lots: float = 1.0) -> DemoBridgePosition:
    return DemoBridgePosition(
        ticket=1,
        symbol=symbol,
        side=Side.BUY,
        lots=lots,
        open_price=100,
        stop_loss=90,
        take_profit=118,
        profit=0,
        open_time="2026.10.01 08:00",
        strategy_comment="TradingNew:test",
    )


def test_allocator_uses_demo_equity_and_existing_absolute_risk_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "absolute_max_risk_fraction", 0.02)
    rows = [
        strategy("BTCUSD", OpportunityMechanism.BREAK_RETEST_REACCEL, 100),
        strategy("EURUSD", OpportunityMechanism.DIRECTIONAL_TRANSITION, 90),
        strategy("XAUUSD", OpportunityMechanism.FAILED_AUCTION_REVERSAL, 20),
    ]
    result = build_portfolio_opportunity_allocation(
        overview(rows, selected=rows[0].strategy_id),
        [],
        {},
        NOW,
    )
    assert result.ready
    assert result.capital_eur == 10_000
    assert result.capital_source == "broker_equity"
    assert result.max_total_open_risk_eur == 200
    assert result.selected_strategy_ids == [rows[0].strategy_id, rows[1].strategy_id]
    assert result.rows[2].decision is AllocationDecision.SKIPPED_RISK_BUDGET
    assert result.uses_daily_loss_cap is False


def test_allocator_counts_exact_bridge_stop_risk_and_blocks_same_symbol(monkeypatch):
    monkeypatch.setattr(settings, "absolute_max_risk_fraction", 0.02)
    btc = strategy("BTCUSD", OpportunityMechanism.BREAK_RETEST_REACCEL, 100)
    eur = strategy("EURUSD", OpportunityMechanism.DIRECTIONAL_TRANSITION, 100)
    result = build_portfolio_opportunity_allocation(
        overview([btc, eur], selected=btc.strategy_id),
        [bridge("BTCUSD")],
        {"BTCUSD": spec("BTCUSD")},
        NOW,
    )
    assert result.current_open_risk_eur == 10
    by_id = {row.strategy_id: row for row in result.rows}
    assert by_id[btc.strategy_id].decision is AllocationDecision.SKIPPED_SYMBOL_CONCENTRATION
    assert by_id[eur.strategy_id].decision is AllocationDecision.ALLOCATED
def test_allocator_surfaces_correlation_concentration_without_new_gate(monkeypatch):
    monkeypatch.setattr(settings, "absolute_max_risk_fraction", 0.02)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    eur = strategy("EURUSD", OpportunityMechanism.DIRECTIONAL_TRANSITION, 60)
    gbp = strategy("GBPUSD", OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION, 60)
    result = build_portfolio_opportunity_allocation(
        overview([eur, gbp], selected=eur.strategy_id),
        [],
        {},
        NOW,
    )
    assert result.selected_strategy_ids == [eur.strategy_id, gbp.strategy_id]
    assert result.rows[1].concentration_warning is True
    assert result.rows[1].projected_bucket_risk_eur == 120


def test_allocator_preserves_five_lot_cap(monkeypatch):
    monkeypatch.setattr(settings, "max_lots_per_trade", 5.0)
    row = strategy(
        "XAUUSD",
        OpportunityMechanism.BREAK_RETEST_REACCEL,
        50,
        lots=5.01,
    )
    result = build_portfolio_opportunity_allocation(overview([row]), [], {}, NOW)
    assert result.selected_strategy_ids == []
    assert result.rows[0].decision is AllocationDecision.SKIPPED_LOT_CAP
@pytest.mark.parametrize("equity,balance", [(0, 0)])
def test_allocator_fails_closed_without_demo_capital(equity, balance):
    row = strategy("BTCUSD", OpportunityMechanism.BREAK_RETEST_REACCEL, 50)
    result = build_portfolio_opportunity_allocation(
        overview([row], equity=equity, balance=balance),
        [],
        {},
        NOW,
    )
    assert result.ready is False
    assert result.capital_eur is None
    assert result.selected_strategy_ids == []


def test_allocator_fails_closed_when_open_bridge_risk_cannot_be_priced():
    row = strategy("EURUSD", OpportunityMechanism.DIRECTIONAL_TRANSITION, 50)
    result = build_portfolio_opportunity_allocation(
        overview([row]),
        [bridge("BTCUSD")],
        {},
        NOW,
    )
    assert result.ready is False
    assert result.risk_unknown_symbols == ["BTCUSD"]


def test_daily_loss_budget_is_not_an_allocator_gate():
    row = strategy("BTCUSD", OpportunityMechanism.BREAK_RETEST_REACCEL, 50)
    current = overview([row])
    current.risk.remaining_daily_loss_budget_eur = 0
    result = build_portfolio_opportunity_allocation(current, [], {}, NOW)
    assert result.ready is True
    assert result.selected_strategy_ids == [row.strategy_id]
    assert result.uses_daily_loss_cap is False
