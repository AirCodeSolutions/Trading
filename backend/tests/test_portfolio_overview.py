import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperState, ShadowPaperTrade
from app.domain.trading import Side
from app.services.portfolio_overview import build_trading_overview

TZ = ZoneInfo("Europe/Athens")


def test_overview_keeps_demo_balance_separate_from_200_eur_reference(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()
    (files_dir / "mt4_data_BTCUSD.json").write_text(
        json.dumps(
            {
                "account": {
                    "is_demo": "1",
                    "balance": "873900",
                    "equity": "873800",
                    "margin": "100",
                    "freeMargin": "873700",
                    "account_number": "must-not-leak",
                },
                "positions": {},
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 19, 17, 0, tzinfo=TZ),
    )

    assert overview.broker is not None
    assert overview.broker.balance == 873900
    assert overview.risk.reference_capital_eur == 200
    assert overview.portfolio.action == "no_trade"
    assert overview.qualifications == []
    assert overview.paper_strategies == []


def test_parallel_shadow_losses_do_not_consume_selected_portfolio_budget(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    state_path = runtime_dir / "BTCUSD_failed_auction_paper_state.json"
    trades_path = runtime_dir / "BTCUSD_failed_auction_paper_trades.jsonl"
    state_path.write_text(ShadowPaperState().model_dump_json(), encoding="utf-8")
    trade = ShadowPaperTrade(
        trade_id="research-loss",
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        side=Side.BUY,
        signal_at=datetime(2026, 9, 19, 9, 0, tzinfo=TZ),
        entry_bar_at=datetime(2026, 9, 19, 9, 0, tzinfo=TZ),
        opened_at=datetime(2026, 9, 19, 9, 1, tzinfo=TZ),
        entry_price=100,
        stop_price=99,
        target_price=101.5,
        spread_at_entry=0.1,
        lots=0.01,
        risk_eur=2,
        risk_distance=1,
        target_r=1.5,
        max_holding_bars=12,
        status=PaperTradeStatus.STOP,
        exit_at=datetime(2026, 9, 19, 9, 10, tzinfo=TZ),
        exit_price=99,
        result_r=-1,
        pnl_eur=-2,
        bars_held=2,
    )
    trades_path.write_text(trade.model_dump_json() + "\n", encoding="utf-8")

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 19, 17, 0, tzinfo=TZ),
    )

    assert overview.risk.research_paper_closed_pnl_eur == -2
    assert overview.risk.selected_daily_pnl_eur == 0
    assert overview.risk.remaining_daily_loss_budget_eur == 6
    assert overview.portfolio.action == "no_trade"
