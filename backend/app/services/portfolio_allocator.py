from collections.abc import Mapping, Sequence
from datetime import datetime

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.demo_execution import DemoBridgePosition
from app.domain.portfolio import (
    PaperStrategyRuntime,
    ProspectiveQualificationState,
    TradingOverview,
)
from app.domain.portfolio_allocator import (
    AllocationDecision,
    CorrelationBucket,
    PortfolioAllocationRow,
    PortfolioOpportunityAllocationReport,
)
from app.services.capital_risk import monetary_loss_per_lot


def _bucket(symbol: str) -> CorrelationBucket:
    normalized = symbol.upper()
    if normalized == "BTCUSD":
        return CorrelationBucket.CRYPTO_USD
    if normalized in {"EURUSD", "GBPUSD"}:
        return CorrelationBucket.USD_FX
    return CorrelationBucket.USD_METALS
def _capital(overview: TradingOverview) -> tuple[float | None, str]:
    broker = overview.broker
    if broker is None or not broker.is_demo:
        return None, "unavailable"
    if broker.equity > 0:
        return broker.equity, "broker_equity"
    if broker.balance > 0:
        return broker.balance, "broker_balance"
    return None, "unavailable"


def _bridge_risk(
    positions: Sequence[DemoBridgePosition],
    specs: Mapping[str, BrokerSymbolSpec],
) -> tuple[float, dict[str, float], list[str]]:
    total = 0.0
    buckets: dict[str, float] = {}
    missing: set[str] = set()
    for position in positions:
        spec = specs.get(position.symbol.upper())
        if spec is None or position.stop_loss <= 0:
            missing.add(position.symbol.upper())
            continue
        distance = abs(position.open_price - position.stop_loss)
        risk = monetary_loss_per_lot(spec, distance) * position.lots
        total += risk
        bucket = _bucket(position.symbol).value
        buckets[bucket] = buckets.get(bucket, 0.0) + risk
    return total, buckets, sorted(missing)
def _candidate_priority(
    row: PaperStrategyRuntime,
    selected_strategy_id: str | None,
) -> tuple[float, float, float, float, float, float]:
    selected = 1.0 if row.strategy_id == selected_strategy_id else 0.0
    prospective = (
        2.0
        if row.qualification.state == ProspectiveQualificationState.SUPPORTS_DEMO
        else 1.0
        if row.qualification.state == ProspectiveQualificationState.COLLECTING
        else 0.0
    )
    historical = row.historical_weakest_expectancy_r or 0.0
    return (
        selected,
        prospective,
        row.qualification.expectancy_r,
        row.qualification.profit_factor,
        -row.qualification.max_drawdown_r,
        historical,
    )


def build_portfolio_opportunity_allocation(
    overview: TradingOverview,
    bridge_positions: Sequence[DemoBridgePosition],
    specs: Mapping[str, BrokerSymbolSpec],
    now: datetime,
) -> PortfolioOpportunityAllocationReport:
    capital, capital_source = _capital(overview)
    max_fraction = settings.absolute_max_risk_fraction
    current_risk, bucket_risk, missing = _bridge_risk(bridge_positions, specs)
    if capital is None:
        return PortfolioOpportunityAllocationReport(
            at=now,
            ready=False,
            capital_source=capital_source,
            max_total_open_risk_fraction=max_fraction,
            current_open_risk_eur=current_risk,
            bridge_open_positions=len(bridge_positions),
            bucket_risk_eur=bucket_risk,
            risk_unknown_symbols=missing,
            reason="DEMO broker equity/balance is unavailable; allocation fails closed",
        )

    max_total_risk = capital * max_fraction
    current_fraction = current_risk / capital
    if missing or current_risk > max_total_risk + 1e-9:
        return PortfolioOpportunityAllocationReport(
            at=now,
            ready=False,
            capital_eur=capital,
            capital_source=capital_source,
            max_total_open_risk_fraction=max_fraction,
            max_total_open_risk_eur=max_total_risk,
            current_open_risk_eur=current_risk,
            current_open_risk_fraction=current_fraction,
            bridge_open_positions=len(bridge_positions),
            bucket_risk_eur=bucket_risk,
            risk_unknown_symbols=missing,
            reason="current Trading-New open risk cannot be proven inside the aggregate risk ceiling",
        )

    rows: list[PortfolioAllocationRow] = []
    selected_ids: list[str] = []
    selected_symbols: set[str] = set()
    bridge_symbols = {position.symbol.upper() for position in bridge_positions}
    projected_total = current_risk
    projected_buckets = dict(bucket_risk)
    candidates = [
        row
        for row in overview.paper_strategies
        if row.summary.open_trade is not None
    ]
    candidates.sort(
        key=lambda row: _candidate_priority(
            row,
            overview.portfolio.selected_strategy_id,
        ),
        reverse=True,
    )

    for row in candidates:
        trade = row.summary.open_trade
        assert trade is not None
        symbol = trade.symbol.upper()
        bucket = _bucket(symbol)
        decision = AllocationDecision.ALLOCATED
        reason = "fits existing concurrent risk ceiling"
        if not row.paper_entry_allowed:
            decision = AllocationDecision.SKIPPED_NOT_ELIGIBLE
            reason = "existing admission/prospective contract does not allow PAPER entry"
        elif trade.lots > settings.max_lots_per_trade + 1e-12:
            decision = AllocationDecision.SKIPPED_LOT_CAP
            reason = "trade exceeds existing max lots per trade"
        elif symbol in bridge_symbols or symbol in selected_symbols:
            decision = AllocationDecision.SKIPPED_SYMBOL_CONCENTRATION
            reason = "one Trading-New position per symbol"
        elif projected_total + trade.risk_eur > max_total_risk + 1e-9:
            decision = AllocationDecision.SKIPPED_RISK_BUDGET
            reason = (
                "aggregate concurrent open risk would exceed "
                "existing absolute risk ceiling"
            )

        allocated_risk = (
            trade.risk_eur
            if decision == AllocationDecision.ALLOCATED
            else 0.0
        )
        candidate_total = projected_total + allocated_risk
        candidate_bucket = (
            projected_buckets.get(bucket.value, 0.0) + allocated_risk
        )
        concentration_warning = (
            candidate_bucket / capital
            > settings.risk_per_trade_fraction + 1e-12
        )

        if decision == AllocationDecision.ALLOCATED:
            projected_total = candidate_total
            projected_buckets[bucket.value] = candidate_bucket
            selected_symbols.add(symbol)
            selected_ids.append(row.strategy_id)

        rows.append(
            PortfolioAllocationRow(
                strategy_id=row.strategy_id,
                symbol=symbol,
                mechanism=row.mechanism,
                side=trade.side,
                risk_eur=trade.risk_eur,
                lots=trade.lots,
                correlation_bucket=bucket,
                decision=decision,
                reason=reason,
                projected_total_open_risk_eur=candidate_total,
                projected_total_open_risk_fraction=candidate_total / capital,
                projected_bucket_risk_eur=candidate_bucket,
                concentration_warning=concentration_warning,
            )
        )

    return PortfolioOpportunityAllocationReport(
        at=now,
        ready=True,
        capital_eur=capital,
        capital_source=capital_source,
        max_total_open_risk_fraction=max_fraction,
        max_total_open_risk_eur=max_total_risk,
        current_open_risk_eur=current_risk,
        current_open_risk_fraction=current_fraction,
        bridge_open_positions=len(bridge_positions),
        selected_strategy_ids=selected_ids,
        primary_strategy_id=selected_ids[0] if selected_ids else None,
        bucket_risk_eur=projected_buckets,
        risk_unknown_symbols=missing,
        uses_daily_loss_cap=False,
        rows=rows,
        reason=(
            "allocation uses current DEMO equity/balance and existing "
            "concurrent risk ceilings; no daily loss veto"
        ),
    )
