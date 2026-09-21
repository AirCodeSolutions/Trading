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
from app.domain.shadow_paper import PaperTradeStatus
from app.domain.trading import Side
from app.services.shadow_paper import (
    advance_shadow_paper_book,
    create_paper_trade,
    load_shadow_paper_summary,
    resolve_open_trade,
)

TZ = ZoneInfo("Europe/Athens")
START = datetime(2026, 9, 19, 13, 0, tzinfo=TZ)


def spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="BTCUSD",
        bid=100.0,
        ask=100.1,
        tick_size=0.01,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=10,
        lot_step=0.01,
        margin_required=10,
    )


def diagnostic() -> ShadowOpportunityDiagnostic:
    return ShadowOpportunityDiagnostic(
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
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
        base_risk=ShadowSizingSnapshot(
            risk_fraction=0.01,
            approved=True,
            reason="approved",
            lots=0.01,
            expected_loss_eur=2.0,
            spread_to_stop=0.1,
        ),
        max_risk=ShadowSizingSnapshot(
            risk_fraction=0.02,
            approved=True,
            reason="approved",
            lots=0.02,
            expected_loss_eur=4.0,
            spread_to_stop=0.1,
        ),
        reason="test",
    )


def bar(
    index: int,
    *,
    high: float = 100.5,
    low: float = 99.8,
    close: float = 100.2,
) -> MarketBar:
    return MarketBar(
        symbol="BTCUSD",
        timeframe=Timeframe.M5,
        timestamp=START + timedelta(minutes=5 * (index + 1)),
        open=100.1,
        high=high,
        low=low,
        close=close,
        volume=100,
    )


def test_stop_wins_when_stop_and_target_touch_same_m5_bar() -> None:
    trade = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )
    resolved = resolve_open_trade(
        trade,
        [bar(1, high=102.2, low=98.9, close=101.0)],
    )

    assert resolved.status == PaperTradeStatus.STOP
    assert resolved.result_r == -1.0
    assert resolved.pnl_eur == -2.0


def test_target_resolves_at_frozen_1_8r() -> None:
    trade = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )
    resolved = resolve_open_trade(
        trade,
        [bar(1, high=102.0, low=99.5, close=101.9)],
    )

    assert resolved.status == PaperTradeStatus.TARGET
    assert resolved.result_r == 1.8
    assert resolved.pnl_eur == 3.6


def test_timeout_marks_to_market_after_18_closed_bars() -> None:
    trade = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )
    bars = [
        bar(index, high=100.6, low=99.6, close=100.6)
        for index in range(1, 19)
    ]

    resolved = resolve_open_trade(trade, bars)

    assert resolved.status == PaperTradeStatus.TIMEOUT
    assert resolved.bars_held == 18
    assert resolved.result_r == 0.5
    assert resolved.pnl_eur == 1.0


def test_advance_deduplicates_same_signal_and_persists_summary(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    trades_path = tmp_path / "trades.jsonl"
    diag = diagnostic()

    first = advance_shadow_paper_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        trades_path=trades_path,
        evaluated_at=diag.evaluated_at,
    )
    second = advance_shadow_paper_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        trades_path=trades_path,
        evaluated_at=diag.evaluated_at + timedelta(seconds=30),
    )

    assert first.open_trade is not None
    assert second.open_trade is not None
    assert first.open_trade.trade_id == second.open_trade.trade_id

    summary = load_shadow_paper_summary(state_path, trades_path)
    assert summary.closed_trades == 0
    assert summary.open_trade is not None


def test_rejected_strategy_does_not_open_new_paper_trade(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    trades_path = tmp_path / "trades.jsonl"
    diag = diagnostic()

    result = advance_shadow_paper_book(
        diagnostic=diag,
        spec=spec(),
        bars_m5=[],
        state_path=state_path,
        trades_path=trades_path,
        evaluated_at=diag.evaluated_at,
        allow_new_entries=False,
    )

    assert result.open_trade is None
    assert result.closed_trades == 0


def test_partial_entry_bar_is_never_used_for_outcome() -> None:
    trade = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    )

    resolved = resolve_open_trade(
        trade,
        [
            bar(0, high=102.2, low=98.9, close=100.0),
            bar(1, high=100.5, low=99.8, close=100.2),
        ],
    )

    assert resolved.status == PaperTradeStatus.OPEN
    assert resolved.bars_held == 1



def test_summary_separates_legacy_and_post_cutover_evidence(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    trades_path = tmp_path / "trades.jsonl"
    state_path.write_text("{}", encoding="utf-8")

    legacy = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=5, seconds=2),
    ).model_copy(
        update={
            "status": PaperTradeStatus.STOP,
            "exit_at": START + timedelta(minutes=10),
            "exit_price": 99.1,
            "result_r": -1.0,
            "pnl_eur": -2.0,
            "bars_held": 1,
        }
    )
    valid = create_paper_trade(
        diagnostic=diagnostic(),
        spec=spec(),
        evaluated_at=START + timedelta(minutes=20, seconds=2),
    ).model_copy(
        update={
            "trade_id": "post-cutover",
            "signal_at": START + timedelta(minutes=20),
            "entry_bar_at": START + timedelta(minutes=20),
            "status": PaperTradeStatus.TARGET,
            "exit_at": START + timedelta(minutes=25),
            "exit_price": 101.9,
            "result_r": 1.8,
            "pnl_eur": 3.6,
            "bars_held": 1,
        }
    )
    trades_path.write_text(
        legacy.model_dump_json() + "\n" + valid.model_dump_json() + "\n",
        encoding="utf-8",
    )

    summary = load_shadow_paper_summary(
        state_path,
        trades_path,
        evidence_cutover_at=START + timedelta(minutes=15),
    )

    assert summary.closed_trades == 1
    assert summary.wins == 1
    assert summary.losses == 0
    assert summary.total_r == 1.8
    assert summary.total_pnl_eur == 3.6
    assert summary.legacy_trades == 1
    assert summary.legacy_total_r == -1.0
    assert summary.legacy_pnl_eur == -2.0
    assert [trade.trade_id for trade in summary.recent_trades] == ["post-cutover"]
