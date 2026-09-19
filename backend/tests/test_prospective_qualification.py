from app.domain.shadow_paper import ShadowPaperSummary
from app.services.prospective_qualification import assess_prospective


def summary(
    trades: int,
    expectancy: float,
    pf: float,
    drawdown: float,
) -> ShadowPaperSummary:
    return ShadowPaperSummary(
        closed_trades=trades,
        wins=0,
        losses=0,
        total_r=expectancy * trades,
        expectancy_r=expectancy,
        profit_factor=pf,
        max_drawdown_r=drawdown,
        total_pnl_eur=0,
    )


def test_prospective_stays_collecting_before_minimum_sample() -> None:
    result = assess_prospective("BTCUSD:test", summary(19, 0.5, 2.0, 1.0))

    assert result.state == "collecting"


def test_prospective_can_support_demo_but_does_not_activate_strategy() -> None:
    result = assess_prospective("BTCUSD:test", summary(20, 0.2, 1.4, 3.0))

    assert result.state == "supports_demo"
    assert "demo" in result.reason


def test_prospective_fails_negative_expectancy() -> None:
    result = assess_prospective("BTCUSD:test", summary(20, -0.1, 1.4, 3.0))

    assert result.state == "failed"
