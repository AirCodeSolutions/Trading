import pytest

from app.domain.broker import BrokerSymbolSpec, MarketQualityRequest, PositionSizeRequest
from app.services.capital_risk import size_position
from app.services.market_quality import assess_market


def test_xau_m15_atr_stop_is_too_coarse_for_400_eur_account() -> None:
    spec = BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4344.70,
        ask=4344.98,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=379.10,
    )
    result = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=4344.98,
            stop=4344.98 - 11.582857,
        )
    )
    assert result.approved is False
    assert "minimum broker lot" in result.reason
    assert result.min_lot_loss_eur == pytest.approx(11.582857, rel=1e-6)


def test_xau_m15_atr_stop_is_approved_with_demo_broker_equity() -> None:
    spec = BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=4344.70,
        ask=4344.98,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=379.10,
    )
    result = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=4344.98,
            stop=4344.98 - 11.582857,
            capital_eur=873859.85,
        )
    )

    assert result.approved is True
    assert result.risk_budget_eur == pytest.approx(8738.5985)
    assert result.lots == pytest.approx(7.54)
    assert result.expected_loss_eur <= result.risk_budget_eur


def test_btc_m15_atr_stop_can_fit_absolute_two_percent_cap() -> None:
    spec = BrokerSymbolSpec(
        symbol="BTCUSD",
        bid=80543.47,
        ask=80567.97,
        tick_size=0.01,
        tick_value=0.00872524,
        min_lot=0.01,
        max_lot=1000,
        lot_step=0.01,
        margin_required=140.59,
    )
    result = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=80567.97,
            stop=80567.97 - 372.780714,
            requested_risk_fraction=0.02,
        )
    )
    assert result.approved is True
    assert result.lots == pytest.approx(0.02)
    assert result.expected_loss_eur < 8.0


def test_eurusd_m15_atr_stop_fits_default_risk_but_is_costly() -> None:
    spec = BrokerSymbolSpec(
        symbol="EURUSD",
        bid=1.14609,
        ask=1.14618,
        tick_size=0.00001,
        tick_value=0.87253183,
        min_lot=0.01,
        max_lot=10000,
        lot_step=0.01,
        margin_required=100.0,
    )
    result = size_position(
        PositionSizeRequest(
            spec=spec,
            entry=1.14618,
            stop=1.14618 - 0.00064,
        )
    )
    assert result.approved is True
    assert result.lots == pytest.approx(0.07)
    assert result.spread_to_stop == pytest.approx(0.140625, rel=1e-5)


def test_market_quality_separates_execution_fit_from_strategy_edge() -> None:
    btc = BrokerSymbolSpec(
        symbol="BTCUSD",
        bid=80543.47,
        ask=80567.97,
        tick_size=0.01,
        tick_value=0.00872524,
        min_lot=0.01,
        max_lot=1000,
        lot_step=0.01,
        margin_required=140.59,
    )
    result = assess_market(
        MarketQualityRequest(
            spec=btc,
            atr_m5=120.0,
            atr_m15=372.780714,
        )
    )
    assert result.eligible_for_m15_research is True
    assert result.absolute_risk_feasible is True
    assert result.default_risk_feasible is True
    assert result.min_lot_loss_atr_m15_eur == pytest.approx(3.252601197, rel=1e-6)
    assert result.required_capital_base_risk_eur == pytest.approx(325.2601197, rel=1e-6)
    assert result.required_capital_max_risk_eur == pytest.approx(162.6300599, rel=1e-6)
    assert result.minimum_feasible_risk_fraction == pytest.approx(0.008131503, rel=1e-6)
    assert result.execution_quality_score > 0
