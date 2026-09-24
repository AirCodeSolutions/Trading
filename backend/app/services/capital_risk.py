from decimal import ROUND_FLOOR, Decimal

from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec, PositionSizeRequest, PositionSizeResult


def _floor_to_step(value: float, step: float) -> float:
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    units = (decimal_value / decimal_step).to_integral_value(rounding=ROUND_FLOOR)
    return float(units * decimal_step)


def monetary_loss_per_lot(spec: BrokerSymbolSpec, price_distance: float) -> float:
    return price_distance / spec.tick_size * spec.tick_value


def size_position(request: PositionSizeRequest) -> PositionSizeResult:
    risk_fraction = request.requested_risk_fraction or settings.risk_per_trade_fraction
    stop_distance = abs(request.entry - request.stop)
    spread = request.spec.spread

    if risk_fraction > settings.absolute_max_risk_fraction:
        return _rejected(
            request,
            risk_fraction,
            stop_distance,
            spread,
            "requested risk exceeds absolute policy limit",
        )

    if stop_distance <= 0:
        return _rejected(request, risk_fraction, stop_distance, spread, "stop distance must be > 0")

    spread_to_stop = spread / stop_distance
    if spread_to_stop > settings.max_spread_to_stop:
        return _rejected(
            request,
            risk_fraction,
            stop_distance,
            spread,
            "spread consumes too much of the stop distance",
        )

    capital_eur = request.capital_eur or settings.reference_capital_eur
    risk_budget = capital_eur * risk_fraction
    loss_per_lot = monetary_loss_per_lot(request.spec, stop_distance)
    min_lot_loss = loss_per_lot * request.spec.min_lot

    if min_lot_loss > risk_budget:
        return _rejected(
            request,
            risk_fraction,
            stop_distance,
            spread,
            "minimum broker lot exceeds the risk budget",
            min_lot_loss=min_lot_loss,
        )

    raw_lots = risk_budget / loss_per_lot
    lots = _floor_to_step(min(raw_lots, request.spec.max_lot), request.spec.lot_step)
    if lots < request.spec.min_lot:
        return _rejected(
            request,
            risk_fraction,
            stop_distance,
            spread,
            "rounded size falls below the broker minimum lot",
            raw_lots=raw_lots,
            min_lot_loss=min_lot_loss,
        )

    expected_loss = loss_per_lot * lots
    margin = request.spec.margin_required * lots
    max_margin = capital_eur * settings.max_margin_fraction
    if margin > max_margin:
        return _rejected(
            request,
            risk_fraction,
            stop_distance,
            spread,
            "estimated margin exceeds capital policy",
            raw_lots=raw_lots,
            lots=lots,
            expected_loss=expected_loss,
            min_lot_loss=min_lot_loss,
            margin=margin,
        )

    return PositionSizeResult(
        approved=True,
        reason="risk and execution constraints satisfied",
        risk_fraction=risk_fraction,
        risk_budget_eur=risk_budget,
        stop_distance=stop_distance,
        spread=spread,
        spread_to_stop=spread_to_stop,
        raw_lots=raw_lots,
        lots=lots,
        expected_loss_eur=expected_loss,
        min_lot_loss_eur=min_lot_loss,
        estimated_margin_eur=margin,
    )


def _rejected(
    request: PositionSizeRequest,
    risk_fraction: float,
    stop_distance: float,
    spread: float,
    reason: str,
    *,
    raw_lots: float = 0,
    lots: float = 0,
    expected_loss: float = 0,
    min_lot_loss: float = 0,
    margin: float = 0,
) -> PositionSizeResult:
    capital_eur = request.capital_eur or settings.reference_capital_eur
    risk_budget = capital_eur * risk_fraction
    spread_to_stop = spread / stop_distance if stop_distance > 0 else 0
    if min_lot_loss == 0 and stop_distance > 0:
        min_lot_loss = monetary_loss_per_lot(request.spec, stop_distance) * request.spec.min_lot
    return PositionSizeResult(
        approved=False,
        reason=reason,
        risk_fraction=risk_fraction,
        risk_budget_eur=risk_budget,
        stop_distance=stop_distance,
        spread=spread,
        spread_to_stop=spread_to_stop,
        raw_lots=raw_lots,
        lots=lots,
        expected_loss_eur=expected_loss,
        min_lot_loss_eur=min_lot_loss,
        estimated_margin_eur=margin,
    )
