import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperState, ShadowPaperTrade
from app.domain.trading import Side
from app.services.portfolio_overview import build_trading_overview

TZ = ZoneInfo("Europe/Athens")


def test_overview_keeps_demo_balance_separate_from_400_eur_reference(
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
    assert overview.risk.reference_capital_eur == 400
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

    assert overview.risk.research_paper_closed_pnl_eur == 0
    assert overview.risk.research_paper_total_r == 0
    assert overview.risk.research_paper_legacy_closed_pnl_eur == -2
    assert overview.risk.research_paper_legacy_total_r == -1
    assert overview.risk.research_paper_legacy_trades == 1
    assert overview.risk.selected_daily_pnl_eur == 0
    assert overview.risk.remaining_daily_loss_budget_eur == 12
    assert overview.portfolio.action == "no_trade"


def test_overview_exposes_historical_paper_collection_status(tmp_path: Path) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    state_path = runtime_dir / "GBPUSD_directional_pullback_paper_state.json"
    state_path.write_text(ShadowPaperState().model_dump_json(), encoding="utf-8")
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "GBPUSD:directional_pullback_resumption": {
                    "strategy_id": "GBPUSD:directional_pullback_resumption",
                    "state": "shadow",
                    "reason": "insufficient independent validation evidence",
                    "weakest_expectancy_r": -0.24,
                    "worst_drawdown_r": 2.7,
                    "paper_collection_candidate": True,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 21, 17, 0, tzinfo=TZ),
    )

    row = next(
        item
        for item in overview.paper_strategies
        if item.strategy_id == "GBPUSD:directional_pullback_resumption"
    )
    assert row.historical_state == "shadow"
    assert row.historical_weakest_expectancy_r == -0.24
    assert row.paper_collection_candidate is True
    assert row.paper_entry_allowed is True


def test_open_paper_collection_candidate_becomes_demo_collection(tmp_path: Path) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    now = datetime(2026, 9, 21, 17, 0, tzinfo=TZ)
    trade = ShadowPaperTrade(
        trade_id="gbp-collection-1",
        symbol="GBPUSD",
        mechanism=OpportunityMechanism.DIRECTIONAL_PULLBACK_RESUMPTION,
        side=Side.BUY,
        signal_at=now,
        entry_bar_at=now,
        opened_at=now,
        entry_price=1.34,
        stop_price=1.338,
        target_price=1.343,
        spread_at_entry=0.00011,
        lots=0.01,
        risk_eur=2.0,
        risk_distance=0.002,
        target_r=1.5,
        max_holding_bars=12,
    )
    (runtime_dir / "GBPUSD_directional_pullback_paper_state.json").write_text(
        ShadowPaperState(open_trade=trade).model_dump_json(),
        encoding="utf-8",
    )
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "GBPUSD:directional_pullback_resumption": {
                    "strategy_id": "GBPUSD:directional_pullback_resumption",
                    "state": "shadow",
                    "reason": "under-sampled",
                    "weakest_expectancy_r": -0.24,
                    "worst_drawdown_r": 2.7,
                    "paper_collection_candidate": True,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(files_dir, runtime_dir, now)

    assert overview.portfolio.action == "demo_collection"
    assert overview.portfolio.selected_strategy_id == "GBPUSD:directional_pullback_resumption"
    assert overview.risk.selected_open_risk_eur == 2.0



def test_overview_exposes_positive_weakest_shadow_as_paper_eligible(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    (runtime_dir / "BTCUSD_break_retest_paper_state.json").write_text(
        ShadowPaperState().model_dump_json(),
        encoding="utf-8",
    )
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "BTCUSD:break_retest_reaccel": {
                    "strategy_id": "BTCUSD:break_retest_reaccel",
                    "state": "shadow",
                    "reason": "insufficient independent validation evidence",
                    "weakest_expectancy_r": 0.24,
                    "worst_drawdown_r": 3.0,
                    "paper_collection_candidate": False,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 22, 8, 0, tzinfo=TZ),
    )

    row = next(
        item
        for item in overview.paper_strategies
        if item.strategy_id == "BTCUSD:break_retest_reaccel"
    )
    assert row.paper_collection_candidate is False
    assert row.historical_weakest_expectancy_r == 0.24
    assert row.paper_entry_allowed is True
    assert overview.portfolio.action == "no_trade"
    assert overview.portfolio.reason == (
        "1 PAPER-eligible SHADOW strategies are waiting for an executable PAPER trade"
    )


def test_overview_never_marks_rejected_admission_as_paper_entry_allowed(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    (runtime_dir / "XAUUSD_failed_auction_paper_state.json").write_text(
        ShadowPaperState().model_dump_json(),
        encoding="utf-8",
    )
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "XAUUSD:failed_auction_reversal": {
                    "strategy_id": "XAUUSD:failed_auction_reversal",
                    "state": "rejected",
                    "reason": "non-positive expectancy in validation or holdout",
                    "weakest_expectancy_r": -0.09,
                    "worst_drawdown_r": 9.7,
                    "paper_collection_candidate": True,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(
        files_dir,
        runtime_dir,
        datetime(2026, 9, 22, 8, 0, tzinfo=TZ),
    )

    row = next(
        item
        for item in overview.paper_strategies
        if item.strategy_id == "XAUUSD:failed_auction_reversal"
    )
    assert row.historical_state == "rejected"
    assert row.paper_collection_candidate is True
    assert row.paper_entry_allowed is False

def test_open_positive_weakest_shadow_can_enter_demo_collection(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    now = datetime(2026, 9, 22, 9, 15, tzinfo=TZ)
    trade = ShadowPaperTrade(
        trade_id="btc-break-retest-demo-1",
        symbol="BTCUSD",
        mechanism=OpportunityMechanism.BREAK_RETEST_REACCEL,
        side=Side.BUY,
        signal_at=now,
        entry_bar_at=now,
        opened_at=now,
        entry_price=65000,
        stop_price=64600,
        target_price=65800,
        spread_at_entry=24.5,
        lots=0.01,
        risk_eur=4.0,
        risk_distance=400,
        target_r=2.0,
        max_holding_bars=12,
    )
    (runtime_dir / "BTCUSD_break_retest_paper_state.json").write_text(
        ShadowPaperState(open_trade=trade).model_dump_json(),
        encoding="utf-8",
    )
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "BTCUSD:break_retest_reaccel": {
                    "strategy_id": "BTCUSD:break_retest_reaccel",
                    "state": "shadow",
                    "reason": "insufficient independent validation evidence",
                    "weakest_expectancy_r": 0.24,
                    "worst_drawdown_r": 3.0,
                    "paper_collection_candidate": False,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(files_dir, runtime_dir, now)

    row = next(
        item
        for item in overview.paper_strategies
        if item.strategy_id == "BTCUSD:break_retest_reaccel"
    )
    assert row.paper_entry_allowed is True
    assert row.paper_collection_candidate is False
    assert overview.portfolio.action == "demo_collection"
    assert overview.portfolio.selected_strategy_id == "BTCUSD:break_retest_reaccel"
    assert overview.portfolio.reason == (
        "PAPER-eligible SHADOW has an executable paper trade; "
        "eligible for isolated broker DEMO collection"
    )
    assert overview.risk.selected_open_risk_eur == 4.0


def test_open_rejected_shadow_never_enters_demo_collection(tmp_path: Path) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    runtime_dir.mkdir()

    now = datetime(2026, 9, 22, 9, 20, tzinfo=TZ)
    trade = ShadowPaperTrade(
        trade_id="xau-rejected-open-1",
        symbol="XAUUSD",
        mechanism=OpportunityMechanism.FAILED_AUCTION_REVERSAL,
        side=Side.BUY,
        signal_at=now,
        entry_bar_at=now,
        opened_at=now,
        entry_price=4318,
        stop_price=4312,
        target_price=4327,
        spread_at_entry=0.28,
        lots=0.01,
        risk_eur=6.0,
        risk_distance=6.0,
        target_r=1.5,
        max_holding_bars=12,
    )
    (runtime_dir / "XAUUSD_failed_auction_paper_state.json").write_text(
        ShadowPaperState(open_trade=trade).model_dump_json(),
        encoding="utf-8",
    )
    (runtime_dir / "strategy_admissions.json").write_text(
        json.dumps(
            {
                "XAUUSD:failed_auction_reversal": {
                    "strategy_id": "XAUUSD:failed_auction_reversal",
                    "state": "rejected",
                    "reason": "non-positive expectancy in validation or holdout",
                    "weakest_expectancy_r": -0.09,
                    "worst_drawdown_r": 9.7,
                    "paper_collection_candidate": False,
                }
            }
        ),
        encoding="utf-8",
    )

    overview = build_trading_overview(files_dir, runtime_dir, now)

    row = next(
        item
        for item in overview.paper_strategies
        if item.strategy_id == "XAUUSD:failed_auction_reversal"
    )
    assert row.paper_entry_allowed is False
    assert overview.portfolio.action == "paper_only"
    assert overview.portfolio.selected_strategy_id == "XAUUSD:failed_auction_reversal"
