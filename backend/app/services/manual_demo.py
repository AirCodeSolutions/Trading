from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import ExecutionMode, settings
from app.domain.approval import ProposalStatus
from app.domain.broker import PositionSizeRequest
from app.domain.demo_execution import DemoCloseCommand, DemoOrderCommand
from app.domain.live_market import MarketFeedStatus
from app.domain.macro import MacroGateStatus
from app.domain.manual_demo import (
    ManualDemoSubmitRequest,
    ManualDemoTradePreview,
    ManualDemoTradeRequest,
)
from app.domain.portfolio import TradingOverview
from app.domain.trading import Side
from app.services.capital_risk import size_position
from app.services.demo_execution import (
    CLOSE_COMMAND_FILE,
    COMMAND_FILE,
    POSITIONS_FILE,
    _write_command,
    read_demo_positions,
    read_pending_close_command,
    read_pending_command,
    submit_demo_close_order,
)
from app.services.execution_audit import (
    append_open_command_event,
)
from app.services.mt4_live_quotes import read_live_market_quotes
from app.services.mt4_specs import get_mt4_symbol_spec

MANUAL_STRATEGY_PREFIX = "manual_demo"
MANUAL_POSITION_COMMENT_PREFIX = "TradingNew:manual_demo:"


def build_manual_demo_preview(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    request: ManualDemoTradeRequest,
    now: datetime,
) -> ManualDemoTradePreview:
    symbol = request.symbol.upper()
    reasons: list[str] = []

    if symbol not in {item.upper() for item in settings.session_watch_symbols}:
        reasons.append("symbol is outside the retained trading universe")
    if settings.execution_mode != ExecutionMode.DEMO:
        reasons.append("execution mode is not demo")
    if not settings.demo_execution_bridge_enabled:
        reasons.append("demo execution bridge is disabled")
    if settings.live_trading_enabled:
        reasons.append("live trading must remain disabled for manual demo")
    if overview.broker is None or not overview.broker.is_demo:
        reasons.append("broker account is not confirmed as demo")
    if overview.risk.research_paper_open_positions > 0:
        reasons.append("manual demo is blocked while a PAPER trade is open")
    if macro.blocked:
        reasons.append(macro.reason)

    bridge_positions = read_demo_positions(files_dir / POSITIONS_FILE)
    if bridge_positions:
        reasons.append("Trading-New bridge already has open position")
    if read_pending_command(files_dir / COMMAND_FILE) is not None:
        reasons.append("a demo open command is already pending")
    if read_pending_close_command(files_dir / CLOSE_COMMAND_FILE) is not None:
        reasons.append("a demo close command is already pending")

    quotes = {
        quote.symbol.upper(): quote
        for quote in read_live_market_quotes(
            files_dir,
            now,
            symbols=settings.session_watch_symbols,
        )
    }
    quote = quotes.get(symbol)
    spec = get_mt4_symbol_spec(files_dir, symbol)

    if quote is None:
        reasons.append("live broker quote is unavailable")
    elif quote.status != MarketFeedStatus.LIVE:
        reasons.append("broker quote is stale")

    if spec is None:
        reasons.append("broker symbol spec is unavailable")

    bid = quote.bid if quote is not None else 0.0
    ask = quote.ask if quote is not None else 0.0
    entry = ask if request.side == Side.BUY else bid
    reward_distance = abs(request.take_profit - entry) if entry > 0 else 0.0

    if entry > 0:
        if request.side == Side.BUY:
            if request.stop_loss >= entry:
                reasons.append("BUY stop must be below the live ask")
            if request.take_profit <= entry:
                reasons.append("BUY target must be above the live ask")
        else:
            if request.stop_loss <= entry:
                reasons.append("SELL stop must be above the live bid")
            if request.take_profit >= entry:
                reasons.append("SELL target must be below the live bid")

    sizing = None
    if spec is not None and quote is not None and quote.status == MarketFeedStatus.LIVE and entry > 0:
        live_spec = spec.model_copy(update={"bid": bid, "ask": ask})
        sizing = size_position(
            PositionSizeRequest(
                spec=live_spec,
                entry=entry,
                stop=request.stop_loss,
                requested_risk_fraction=request.risk_fraction,
            )
        )
        if not sizing.approved:
            reasons.append(sizing.reason)
        else:
            if sizing.expected_loss_eur > overview.risk.remaining_daily_loss_budget_eur:
                reasons.append("manual trade risk exceeds remaining daily loss budget")
            if (
                overview.broker is not None
                and sizing.estimated_margin_eur > overview.broker.free_margin
            ):
                reasons.append("estimated margin exceeds broker free margin")

    stop_distance = abs(entry - request.stop_loss) if entry > 0 else 0.0
    reward_risk_ratio = reward_distance / stop_distance if stop_distance > 0 else 0.0

    return ManualDemoTradePreview(
        at=now,
        symbol=symbol,
        side=request.side,
        bid=bid,
        ask=ask,
        entry_price=entry,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        risk_fraction=request.risk_fraction,
        reward_distance=reward_distance,
        reward_risk_ratio=reward_risk_ratio,
        quote_age_seconds=quote.age_seconds if quote is not None else 0.0,
        remaining_daily_loss_budget_eur=overview.risk.remaining_daily_loss_budget_eur,
        approved=not reasons and sizing is not None and sizing.approved,
        reasons=reasons,
        sizing=sizing,
    )


def submit_manual_demo_order(
    *,
    files_dir: Path,
    overview: TradingOverview,
    macro: MacroGateStatus,
    request: ManualDemoSubmitRequest,
    now: datetime,
    audit_path: Path | None = None,
) -> DemoOrderCommand:
    if not request.confirmed:
        raise ValueError("manual demo trade requires explicit confirmation")

    preview = build_manual_demo_preview(
        files_dir=files_dir,
        overview=overview,
        macro=macro,
        request=ManualDemoTradeRequest(
            symbol=request.symbol,
            side=request.side,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            risk_fraction=request.risk_fraction,
        ),
        now=now,
    )
    if not preview.approved or preview.sizing is None:
        raise ValueError("; ".join(preview.reasons) or "manual demo preview is not approved")

    if read_pending_command(files_dir / COMMAND_FILE) is not None:
        raise ValueError("a demo command is already pending")

    command = DemoOrderCommand(
        command_id=uuid4().hex,
        symbol=preview.symbol,
        side=preview.side,
        lots=preview.sizing.lots,
        stop_loss=preview.stop_loss,
        take_profit=preview.take_profit,
        strategy_id=f"{MANUAL_STRATEGY_PREFIX}:{preview.symbol.lower()}",
        issued_at=now,
        magic_number=settings.demo_magic_number,
        slippage_points=settings.demo_max_slippage_points,
        proposal_status=ProposalStatus.AUTHORIZED,
    )
    _write_command(files_dir / COMMAND_FILE, command)
    if audit_path is not None:
        try:
            append_open_command_event(
                audit_path,
                command,
                reference_entry_price=preview.entry_price,
            )
        except OSError:
            pass
    return command


def submit_manual_demo_close(
    *,
    files_dir: Path,
    overview: TradingOverview,
    ticket: int,
    now: datetime,
    audit_path: Path | None = None,
) -> DemoCloseCommand:
    position = next(
        (item for item in read_demo_positions(files_dir / POSITIONS_FILE) if item.ticket == ticket),
        None,
    )
    if position is None:
        raise ValueError("Trading-New bridge ticket is not open")
    if not position.strategy_comment.startswith(MANUAL_POSITION_COMMENT_PREFIX):
        raise ValueError("ticket is not a manual Trading-New position")

    return submit_demo_close_order(
        files_dir=files_dir,
        overview=overview,
        ticket=ticket,
        strategy_id=position.strategy_comment,
        now=now,
        audit_path=audit_path,
    )
