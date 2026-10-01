from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar, Timeframe
from app.domain.opportunity import OpportunityMechanism
from app.domain.regime import MarketRegime
from app.domain.shadow import (
    ShadowOpportunityDiagnostic,
    ShadowSignalState,
    ShadowSizingSnapshot,
)
from app.domain.trading import Side
from app.services.paired_economic_contracts import (
    XAU_SD_CHALLENGER_1_5R,
    XAU_SD_CHAMPION_1R,
    advance_xau_structural_displacement_target_pair,
    build_xau_structural_displacement_target_report,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 10, 1, 12, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="XAUUSD",
        bid=100.0,
        ask=100.1,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=10.0,
    )
def diagnostic() -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE,
        evaluated_at=START + timedelta(minutes=5, seconds=2),
        latest_closed_m5_at=START,
        latest_closed_m15_at=START - timedelta(minutes=15),
        state=ShadowSignalState.SIGNAL_EXECUTABLE,
        side=Side.BUY,
        regime=MarketRegime.DIRECTIONAL,
        regime_direction=1,
        atr_m15=1.5,
        atr_ratio=1.2,
        volatility_percentile=0.7,
        momentum_12_atr=2.0,
        efficiency=0.7,
        structural_stop=99.1,
        target_r=1.0,
        max_holding_bars=12,
        base_risk=ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=True,
            reason="approved",
            lots=5.0,
            expected_loss_eur=5.0,
            spread_to_stop=0.1,
        ),
        max_risk=ShadowSizingSnapshot(
            risk_fraction=0.02,
            approved=True,
            reason="approved",
            lots=5.0,
            expected_loss_eur=10.0,
            spread_to_stop=0.1,
        ),
        reason="test",
    )


def bar(
    index: int,
    *,
    high: float,
    low: float = 99.8,
    close: float = 100.5,
) -> MarketBar:
    return MarketBar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * (index + 2)),
        open=100.1,
        high=high,
        low=low,
        close=close,
        volume=100,
    )
def test_contracts_are_versioned_and_change_only_target_r() -> None:
    assert XAU_SD_CHAMPION_1R.version == 1
    assert XAU_SD_CHAMPION_1R.target_r == 1.0
    assert XAU_SD_CHALLENGER_1_5R.version == 2
    assert XAU_SD_CHALLENGER_1_5R.target_r == 1.5
    assert XAU_SD_CHAMPION_1R.symbol == XAU_SD_CHALLENGER_1_5R.symbol
    assert (
        XAU_SD_CHAMPION_1R.mechanism
        == XAU_SD_CHALLENGER_1_5R.mechanism
    )
    assert (
        XAU_SD_CHAMPION_1R.max_holding_bars
        == XAU_SD_CHALLENGER_1_5R.max_holding_bars
        == 12
    )


def test_pair_opens_with_identical_entry_stop_risk_and_different_target(
    tmp_path: Path,
) -> None:
    report = advance_xau_structural_displacement_target_pair(
        diagnostic=diagnostic(),
        spec=spec(),
        bars_m5=[],
        runtime_dir=tmp_path,
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )

    assert report.open_pair is True
    state_files = sorted(tmp_path.glob("*_paired_state.json"))
    assert len(state_files) == 2
    trades = []
    for state_file in state_files:
        import json

        payload = json.loads(state_file.read_text())
        trades.append(payload["open_trade"])

    assert {trade["target_r"] for trade in trades} == {1.0, 1.5}
    assert len({trade["entry_price"] for trade in trades}) == 1
    assert len({trade["stop_price"] for trade in trades}) == 1
    assert len({trade["lots"] for trade in trades}) == 1
    assert len({trade["risk_eur"] for trade in trades}) == 1
    assert len({trade["opened_at"] for trade in trades}) == 1
def test_no_new_pair_starts_while_only_challenger_remains_open(
    tmp_path: Path,
) -> None:
    diag = diagnostic()
    evaluated_at = START + timedelta(minutes=5, seconds=2)
    advance_xau_structural_displacement_target_pair(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        runtime_dir=tmp_path,
        evaluated_at=evaluated_at,
    )

    first_bar = bar(0, high=101.2)
    report = advance_xau_structural_displacement_target_pair(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[first_bar],
        runtime_dir=tmp_path,
        evaluated_at=evaluated_at + timedelta(minutes=5),
    )

    assert report.paired_trades == 0
    assert report.champion.closed_trades == 0
    assert report.challenger.closed_trades == 0
    assert report.open_pair is True
    assert len(list(tmp_path.glob("*_paired_trades.jsonl"))) == 1

    state_files = sorted(tmp_path.glob("*_paired_state.json"))
    open_trades = [
        file.read_text().count('"open_trade": null') == 0
        for file in state_files
    ]
    assert sum(open_trades) == 1

    second_bar = bar(1, high=101.7)
    report = advance_xau_structural_displacement_target_pair(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[first_bar, second_bar],
        runtime_dir=tmp_path,
        evaluated_at=evaluated_at + timedelta(minutes=10),
    )
    assert report.open_pair is False
    assert report.paired_trades == 1
    assert report.delta_total_r == 0.5
    assert report.comparisons[0].champion_result_r == 1.0
    assert report.comparisons[0].challenger_result_r == 1.5
def test_drain_style_entry_disable_advances_existing_but_starts_no_pair(
    tmp_path: Path,
) -> None:
    diag = diagnostic()
    report = advance_xau_structural_displacement_target_pair(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        runtime_dir=tmp_path,
        evaluated_at=diag.evaluated_at,
        allow_new_entries=False,
    )
    assert report.open_pair is False
    assert list(tmp_path.glob("*_paired_state.json"))
    assert not list(tmp_path.glob("*_paired_trades.jsonl"))


def test_report_is_research_only(tmp_path: Path) -> None:
    report = build_xau_structural_displacement_target_report(tmp_path)
    assert report.broker_authority is False
    assert report.human_review_required is True
    assert report.paired_trades == 0
