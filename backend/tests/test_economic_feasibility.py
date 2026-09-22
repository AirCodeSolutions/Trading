from app.core.config import settings
from app.domain.broker import BrokerSymbolSpec
from app.services.economic_feasibility import (
    _feasible_stop_envelope,
    _summarize_stop_profile,
)


def test_xag_like_envelope_is_impossible_at_400_eur(monkeypatch) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "max_spread_to_stop", 0.15)
    monkeypatch.setattr(settings, "max_margin_fraction", 0.25)

    spec = BrokerSymbolSpec(
        symbol="XAGUSD",
        bid=40.0,
        ask=40.07,
        tick_size=0.001,
        tick_value=5.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=2858.07,
    )

    floor, ceiling, required_capital = _feasible_stop_envelope(
        spec,
        risk_fraction=0.01,
    )

    assert round(floor, 3) == 0.467
    assert round(ceiling, 3) == 0.08
    assert floor > ceiling
    assert required_capital > 2300


def test_stop_profile_separates_spread_and_min_lot_rejections(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    monkeypatch.setattr(settings, "absolute_max_risk_fraction", 0.02)
    monkeypatch.setattr(settings, "max_spread_to_stop", 0.15)
    monkeypatch.setattr(settings, "max_margin_fraction", 0.25)

    spec = BrokerSymbolSpec(
        symbol="TEST",
        bid=100.0,
        ask=100.01,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.1,
        max_lot=100.0,
        lot_step=0.1,
        margin_required=100.0,
    )
    episodes = [
        {"reference_price": 100.0, "atr_m5": 0.1},
        {"reference_price": 100.0, "atr_m5": 1.0},
        {"reference_price": 100.0, "atr_m5": 0.4},
    ]

    summary = _summarize_stop_profile(
        episodes,
        spec=spec,
        risk_fraction=0.01,
        stop_atr_multiple=0.5,
    )

    assert summary.episodes == 3
    assert summary.approved == 1
    assert summary.rejected_spread == 1
    assert summary.rejected_min_lot == 1
    assert summary.rejected_margin == 0
    assert summary.approval_rate == 1 / 3
    assert summary.average_expected_loss_eur > 0


def test_economic_feasibility_snapshot_round_trip(tmp_path) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.domain.economic_feasibility import EconomicFeasibilityReport
    from app.services.economic_feasibility import (
        load_economic_feasibility_report,
        write_economic_feasibility_report,
    )

    report = EconomicFeasibilityReport(
        generated_at=datetime(2026, 9, 22, 12, 0, tzinfo=ZoneInfo("Europe/Athens")),
        reference_capital_eur=400,
        risk_fraction=0.01,
        max_spread_to_stop=0.15,
        max_margin_fraction=0.25,
        stop_atr_multiples=[0.5, 0.75, 1.0, 1.5],
        assets=[],
    )
    path = tmp_path / "economic_feasibility_latest.json"

    write_economic_feasibility_report(path, report)
    loaded = load_economic_feasibility_report(path)

    assert loaded is not None
    assert loaded.reference_capital_eur == 400
    assert loaded.stop_atr_multiples == [0.5, 0.75, 1.0, 1.5]


def test_corrupt_economic_feasibility_snapshot_returns_none(tmp_path) -> None:
    from app.services.economic_feasibility import load_economic_feasibility_report

    path = tmp_path / "economic_feasibility_latest.json"
    path.write_text("{broken", encoding="utf-8")

    assert load_economic_feasibility_report(path) is None
