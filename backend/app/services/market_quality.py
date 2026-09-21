from app.core.config import settings
from app.domain.broker import (
    MarketQualityRequest,
    MarketQualityResult,
    PositionSizeRequest,
)
from app.services.capital_risk import monetary_loss_per_lot, size_position


def assess_market(request: MarketQualityRequest) -> MarketQualityResult:
    spread_m5 = request.spec.spread / request.atr_m5
    spread_m15 = request.spec.spread / request.atr_m15

    default_sizing = size_position(
        PositionSizeRequest(
            spec=request.spec,
            entry=request.spec.ask,
            stop=request.spec.ask - request.atr_m15,
        )
    )
    absolute_sizing = size_position(
        PositionSizeRequest(
            spec=request.spec,
            entry=request.spec.ask,
            stop=request.spec.ask - request.atr_m15,
            requested_risk_fraction=settings.absolute_max_risk_fraction,
        )
    )

    min_lot_loss = (
        monetary_loss_per_lot(request.spec, request.atr_m15) * request.spec.min_lot
    )
    required_base = min_lot_loss / settings.risk_per_trade_fraction
    required_max = min_lot_loss / settings.absolute_max_risk_fraction
    minimum_fraction = min_lot_loss / settings.reference_capital_eur
    cost_score = max(0.0, 1.0 - spread_m15 / settings.max_spread_to_stop)
    capital_score = 1.0 if absolute_sizing.approved else 0.0
    score = round(100 * (0.7 * cost_score + 0.3 * capital_score), 1)

    reasons: list[str] = []
    if spread_m15 > settings.max_spread_to_stop:
        reasons.append("M15 spread/ATR exceeds execution policy")
    if not default_sizing.approved:
        reasons.append(f"default 1R sizing: {default_sizing.reason}")
    if not absolute_sizing.approved:
        reasons.append(f"absolute-risk sizing: {absolute_sizing.reason}")
    if not reasons:
        reasons.append("cost and capital granularity are compatible with M15 research")

    return MarketQualityResult(
        symbol=request.spec.symbol.upper(),
        spread_atr_m5=spread_m5,
        spread_atr_m15=spread_m15,
        min_lot_loss_atr_m15_eur=min_lot_loss,
        required_capital_base_risk_eur=required_base,
        required_capital_max_risk_eur=required_max,
        minimum_feasible_risk_fraction=minimum_fraction,
        default_risk_feasible=default_sizing.approved,
        absolute_risk_feasible=absolute_sizing.approved,
        execution_quality_score=score,
        eligible_for_m15_research=(
            spread_m15 <= settings.max_spread_to_stop and absolute_sizing.approved
        ),
        reasons=reasons,
    )
