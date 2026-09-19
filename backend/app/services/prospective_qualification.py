from app.domain.portfolio import (
    ProspectiveQualification,
    ProspectiveQualificationState,
)
from app.domain.shadow_paper import ShadowPaperSummary


MIN_PROSPECTIVE_TRADES = 20
MIN_PROFIT_FACTOR = 1.05
MAX_DRAWDOWN_R = 12.0


def assess_prospective(
    strategy_id: str,
    summary: ShadowPaperSummary,
) -> ProspectiveQualification:
    if summary.closed_trades < MIN_PROSPECTIVE_TRADES:
        return ProspectiveQualification(
            strategy_id=strategy_id,
            state=ProspectiveQualificationState.COLLECTING,
            closed_trades=summary.closed_trades,
            expectancy_r=summary.expectancy_r,
            profit_factor=summary.profit_factor,
            max_drawdown_r=summary.max_drawdown_r,
            reason="insufficient prospective paper evidence",
        )

    if summary.expectancy_r <= 0:
        return _failed(strategy_id, summary, "non-positive prospective expectancy")
    if summary.profit_factor < MIN_PROFIT_FACTOR:
        return _failed(strategy_id, summary, "prospective profit factor below floor")
    if summary.max_drawdown_r > MAX_DRAWDOWN_R:
        return _failed(strategy_id, summary, "prospective drawdown exceeds policy")

    return ProspectiveQualification(
        strategy_id=strategy_id,
        state=ProspectiveQualificationState.SUPPORTS_DEMO,
        closed_trades=summary.closed_trades,
        expectancy_r=summary.expectancy_r,
        profit_factor=summary.profit_factor,
        max_drawdown_r=summary.max_drawdown_r,
        reason="prospective paper evidence supports demo evaluation",
    )


def _failed(
    strategy_id: str,
    summary: ShadowPaperSummary,
    reason: str,
) -> ProspectiveQualification:
    return ProspectiveQualification(
        strategy_id=strategy_id,
        state=ProspectiveQualificationState.FAILED,
        closed_trades=summary.closed_trades,
        expectancy_r=summary.expectancy_r,
        profit_factor=summary.profit_factor,
        max_drawdown_r=summary.max_drawdown_r,
        reason=reason,
    )
