from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.config import ExecutionMode, settings
from app.domain.broker import BrokerSymbolSpec
from app.domain.live_market import LiveMarketQuote, MarketFeedStatus
from app.domain.macro import MacroGateStatus
from app.domain.manual_demo import ManualDemoSubmitRequest, ManualDemoTradeRequest
from app.domain.portfolio import (
    BrokerDemoSnapshot,
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    TradingOverview,
)
from app.domain.trading import Side
from app.services.demo_execution import read_pending_command
from app.services.manual_demo import (
    build_manual_demo_preview,
    submit_manual_demo_order,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 22, 10, 45, tzinfo=TZ)


def clear_macro() -> MacroGateStatus:
    return MacroGateStatus(
        at=NOW,
        blocked=False,
        active_events=[],
        reason="clear",
    )


def overview(*, open_paper_positions: int = 0) -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=BrokerDemoSnapshot(
            is_demo=True,
            balance=850000,
            equity=850000,
            margin=0,
            free_margin=850000,
            observed_positions=1,
        ),
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=400,
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=0,
            research_paper_open_positions=open_paper_positions,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=12,
            remaining_daily_loss_budget_eur=12,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.NO_TRADE,
            selected_strategy_id=None,
            reason="waiting",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[],
        paper_strategies=[],
    )


def eur_spec() -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        symbol="EURUSD",
        bid=1.1800,
        ask=1.1801,
        tick_size=0.00001,
        tick_value=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        margin_required=1000.0,
    )


def eur_quote(*, status: MarketFeedStatus = MarketFeedStatus.LIVE) -> LiveMarketQuote:
    return LiveMarketQuote(
        symbol="EURUSD",
        as_of=NOW,
        bid=1.1800,
        ask=1.1801,
        mid=1.18005,
        spread=0.0001,
        spread_pct=0.008474,
        digits=5,
        age_seconds=1.0,
        status=status,
        last_closed_m5_at=NOW,
        recent_m5_closes=[],
    )


def configure_demo(monkeypatch) -> None:
    monkeypatch.setattr(settings, "execution_mode", ExecutionMode.DEMO)
    monkeypatch.setattr(settings, "demo_execution_bridge_enabled", True)
    monkeypatch.setattr(settings, "live_trading_enabled", False)
    monkeypatch.setattr(settings, "reference_capital_eur", 400.0)
    monkeypatch.setattr(settings, "risk_per_trade_fraction", 0.01)
    monkeypatch.setattr(settings, "absolute_max_risk_fraction", 0.02)
    monkeypatch.setattr(settings, "max_spread_to_stop", 0.15)
    monkeypatch.setattr(settings, "max_margin_fraction", 0.25)
    monkeypatch.setattr(
        settings,
        "session_watch_symbols",
        ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"),
    )


def patch_market(monkeypatch, *, quote_status: MarketFeedStatus = MarketFeedStatus.LIVE) -> None:
    monkeypatch.setattr(
        "app.services.manual_demo.read_live_market_quotes",
        lambda *args, **kwargs: [eur_quote(status=quote_status)],
    )
    monkeypatch.setattr(
        "app.services.manual_demo.get_mt4_symbol_spec",
        lambda *args, **kwargs: eur_spec(),
    )


def valid_request(*, risk_fraction: float = 0.01) -> ManualDemoTradeRequest:
    return ManualDemoTradeRequest(
        symbol="EURUSD",
        side=Side.BUY,
        stop_loss=1.1790,
        take_profit=1.1820,
        risk_fraction=risk_fraction,
    )


def test_manual_preview_sizes_from_live_quote_and_existing_risk_engine(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=valid_request(),
        now=NOW,
    )

    assert preview.approved is True
    assert preview.entry_price == pytest.approx(1.1801)
    assert preview.reward_risk_ratio > 1
    assert preview.sizing is not None
    assert preview.sizing.approved is True
    assert preview.sizing.expected_loss_eur <= 4.0
    assert preview.sizing.spread_to_stop <= 0.15


def test_manual_preview_rejects_runtime_drain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=valid_request(),
        now=NOW,
        drain_enabled=True,
    )

    assert preview.approved is False
    assert "runtime drain is enabled" in preview.reasons


def test_manual_preview_rejects_risk_above_absolute_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=valid_request(risk_fraction=0.021),
        now=NOW,
    )

    assert preview.approved is False
    assert "requested risk exceeds absolute policy limit" in preview.reasons


def test_manual_preview_rejects_bad_buy_stop_and_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=ManualDemoTradeRequest(
            symbol="EURUSD",
            side=Side.BUY,
            stop_loss=1.1810,
            take_profit=1.1795,
            risk_fraction=0.01,
        ),
        now=NOW,
    )

    assert preview.approved is False
    assert "BUY stop must be below the live ask" in preview.reasons
    assert "BUY target must be above the live ask" in preview.reasons


def test_manual_preview_rejects_stale_quote(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch, quote_status=MarketFeedStatus.STALE)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=valid_request(),
        now=NOW,
    )

    assert preview.approved is False
    assert "broker quote is stale" in preview.reasons


def test_manual_preview_rejects_while_paper_is_open(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    preview = build_manual_demo_preview(
        files_dir=tmp_path,
        overview=overview(open_paper_positions=1),
        macro=clear_macro(),
        request=valid_request(),
        now=NOW,
    )

    assert preview.approved is False
    assert "manual demo is blocked while a PAPER trade is open" in preview.reasons


def test_manual_submit_requires_explicit_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    with pytest.raises(ValueError, match="explicit confirmation"):
        submit_manual_demo_order(
            files_dir=tmp_path,
            overview=overview(),
            macro=clear_macro(),
            request=ManualDemoSubmitRequest(
                **valid_request().model_dump(),
                confirmed=False,
            ),
            now=NOW,
        )

    assert not (tmp_path / "trading_demo_command.csv").exists()


def test_manual_submit_writes_only_risk_sized_demo_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_demo(monkeypatch)
    patch_market(monkeypatch)

    command = submit_manual_demo_order(
        files_dir=tmp_path,
        overview=overview(),
        macro=clear_macro(),
        request=ManualDemoSubmitRequest(
            **valid_request().model_dump(),
            confirmed=True,
        ),
        now=NOW,
    )
    pending = read_pending_command(tmp_path / "trading_demo_command.csv")

    assert pending is not None
    assert pending.command_id == command.command_id
    assert pending.symbol == "EURUSD"
    assert pending.side == Side.BUY
    assert pending.strategy_id == "manual_demo:eurusd"
    assert pending.lots > 0
    assert pending.stop_loss == 1.1790
    assert pending.take_profit == 1.1820


def write_bridge_position(path: Path, *, comment: str) -> None:
    path.write_text(
        "ticket,symbol,side,lots,open_price,stop_loss,take_profit,profit,open_time,comment\n"
        f"321,EURUSD,BUY,0.01,1.1801,1.1790,1.1820,1.25,2026.09.22 10:45,{comment}\n",
        encoding="utf-8",
    )


def test_manual_close_accepts_only_manual_bridge_ticket(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.services.demo_execution import read_pending_close_command
    from app.services.manual_demo import submit_manual_demo_close

    configure_demo(monkeypatch)
    write_bridge_position(
        tmp_path / "trading_demo_positions.csv",
        comment="TradingNew:manual_demo:eurusd",
    )

    command = submit_manual_demo_close(
        files_dir=tmp_path,
        overview=overview(),
        ticket=321,
        now=NOW,
    )
    pending = read_pending_close_command(tmp_path / "trading_demo_close_command.csv")

    assert pending is not None
    assert pending.ticket == 321
    assert command.strategy_id == "TradingNew:manual_demo:eurusd"


def test_manual_close_refuses_auto_bridge_ticket(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.services.manual_demo import submit_manual_demo_close

    configure_demo(monkeypatch)
    write_bridge_position(
        tmp_path / "trading_demo_positions.csv",
        comment="TradingNew:BTCUSD:break_retest_reaccel",
    )

    with pytest.raises(ValueError, match="not a manual Trading-New position"):
        submit_manual_demo_close(
            files_dir=tmp_path,
            overview=overview(),
            ticket=321,
            now=NOW,
        )
