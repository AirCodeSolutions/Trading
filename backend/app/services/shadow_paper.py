from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.broker import BrokerSymbolSpec
from app.domain.market import MarketBar
from app.domain.shadow import ShadowOpportunityDiagnostic, ShadowSignalState
from app.domain.shadow_paper import (
    PaperTradeStatus,
    ShadowPaperState,
    ShadowPaperSummary,
    ShadowPaperTrade,
)
from app.domain.trading import Side

TARGET_R = 1.8
MAX_HOLDING_BARS = 18
RECENT_TRADES_LIMIT = 10


def advance_shadow_paper_book(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    bars_m5: Sequence[MarketBar],
    state_path: Path,
    trades_path: Path,
    evaluated_at: datetime,
) -> ShadowPaperSummary:
    state = load_shadow_paper_state(state_path)

    if state.open_trade is not None:
        resolved = resolve_open_trade(state.open_trade, bars_m5)
        if resolved.status != PaperTradeStatus.OPEN:
            append_closed_trade(trades_path, resolved)
            state.open_trade = None
        else:
            state.open_trade = resolved

    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    if (
        state.open_trade is None
        and diagnostic.state == ShadowSignalState.SIGNAL_EXECUTABLE
        and diagnostic.side is not None
        and diagnostic.structural_stop is not None
        and diagnostic.base_risk is not None
        and diagnostic.base_risk.approved
        and (
            state.last_started_signal_at is None
            or signal_at > state.last_started_signal_at
        )
    ):
        state.open_trade = create_paper_trade(
            diagnostic=diagnostic,
            spec=spec,
            evaluated_at=evaluated_at,
        )
        state.last_started_signal_at = signal_at

    save_shadow_paper_state(state_path, state)
    return load_shadow_paper_summary(state_path, trades_path)


def create_paper_trade(
    *,
    diagnostic: ShadowOpportunityDiagnostic,
    spec: BrokerSymbolSpec,
    evaluated_at: datetime,
) -> ShadowPaperTrade:
    if diagnostic.side is None:
        raise ValueError("paper trade requires a side")
    if diagnostic.structural_stop is None:
        raise ValueError("paper trade requires a structural stop")
    if diagnostic.base_risk is None or not diagnostic.base_risk.approved:
        raise ValueError("paper trade requires approved base-risk sizing")

    side = diagnostic.side
    entry = spec.ask if side == Side.BUY else spec.bid
    stop = diagnostic.structural_stop
    risk_distance = (
        entry - stop if side == Side.BUY else stop - entry
    )
    if risk_distance <= 0:
        raise ValueError("paper trade stop geometry is invalid")

    target = (
        entry + TARGET_R * risk_distance
        if side == Side.BUY
        else entry - TARGET_R * risk_distance
    )
    signal_at = diagnostic.latest_closed_m5_at + timedelta(minutes=5)
    trade_id = (
        f"{diagnostic.symbol}-{diagnostic.mechanism.value}-"
        f"{signal_at.isoformat()}"
    )

    return ShadowPaperTrade(
        trade_id=trade_id,
        symbol=diagnostic.symbol,
        mechanism=diagnostic.mechanism,
        side=side,
        signal_at=signal_at,
        entry_bar_at=signal_at,
        opened_at=evaluated_at,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        spread_at_entry=spec.spread,
        lots=diagnostic.base_risk.lots,
        risk_eur=diagnostic.base_risk.expected_loss_eur,
        risk_distance=risk_distance,
        target_r=TARGET_R,
        max_holding_bars=MAX_HOLDING_BARS,
    )


def resolve_open_trade(
    trade: ShadowPaperTrade,
    bars_m5: Sequence[MarketBar],
) -> ShadowPaperTrade:
    if trade.status != PaperTradeStatus.OPEN:
        return trade

    future_bars = [
        bar for bar in bars_m5 if bar.timestamp >= trade.entry_bar_at
    ][: trade.max_holding_bars]

    for index, bar in enumerate(future_bars, start=1):
        if trade.side == Side.BUY:
            stop_hit = bar.low <= trade.stop_price
            target_hit = bar.high >= trade.target_price
        else:
            ask_high = bar.high + trade.spread_at_entry
            ask_low = bar.low + trade.spread_at_entry
            stop_hit = ask_high >= trade.stop_price
            target_hit = ask_low <= trade.target_price

        if stop_hit:
            return _close_trade(
                trade,
                status=PaperTradeStatus.STOP,
                exit_at=bar.timestamp,
                exit_price=trade.stop_price,
                result_r=-1.0,
                bars_held=index,
            )
        if target_hit:
            return _close_trade(
                trade,
                status=PaperTradeStatus.TARGET,
                exit_at=bar.timestamp,
                exit_price=trade.target_price,
                result_r=trade.target_r,
                bars_held=index,
            )

    if len(future_bars) < trade.max_holding_bars:
        return trade.model_copy(update={"bars_held": len(future_bars)})

    last = future_bars[-1]
    if trade.side == Side.BUY:
        exit_price = last.close
        result_r = (exit_price - trade.entry_price) / trade.risk_distance
    else:
        exit_price = last.close + trade.spread_at_entry
        result_r = (trade.entry_price - exit_price) / trade.risk_distance

    return _close_trade(
        trade,
        status=PaperTradeStatus.TIMEOUT,
        exit_at=last.timestamp,
        exit_price=exit_price,
        result_r=result_r,
        bars_held=trade.max_holding_bars,
    )


def _close_trade(
    trade: ShadowPaperTrade,
    *,
    status: PaperTradeStatus,
    exit_at: datetime,
    exit_price: float,
    result_r: float,
    bars_held: int,
) -> ShadowPaperTrade:
    return trade.model_copy(
        update={
            "status": status,
            "exit_at": exit_at,
            "exit_price": exit_price,
            "result_r": result_r,
            "pnl_eur": result_r * trade.risk_eur,
            "bars_held": bars_held,
        }
    )


def load_shadow_paper_state(path: Path) -> ShadowPaperState:
    if not path.is_file():
        return ShadowPaperState()
    try:
        return ShadowPaperState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ShadowPaperState()


def save_shadow_paper_state(path: Path, state: ShadowPaperState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def append_closed_trade(path: Path, trade: ShadowPaperTrade) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(trade.model_dump_json())
        handle.write("\n")


def load_closed_trades(path: Path) -> list[ShadowPaperTrade]:
    if not path.is_file():
        return []
    trades: list[ShadowPaperTrade] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                trade = ShadowPaperTrade.model_validate_json(line)
            except ValueError:
                continue
            if trade.status != PaperTradeStatus.OPEN:
                trades.append(trade)
    return trades


def load_shadow_paper_summary(
    state_path: Path,
    trades_path: Path,
) -> ShadowPaperSummary:
    state = load_shadow_paper_state(state_path)
    trades = load_closed_trades(trades_path)
    results = [
        trade.result_r for trade in trades if trade.result_r is not None
    ]
    gains = sum(result for result in results if result > 0)
    losses = -sum(result for result in results if result < 0)
    profit_factor = gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for result in results:
        equity += result
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return ShadowPaperSummary(
        closed_trades=len(trades),
        wins=sum(result > 0 for result in results),
        losses=sum(result < 0 for result in results),
        total_r=sum(results),
        expectancy_r=(sum(results) / len(results)) if results else 0.0,
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        total_pnl_eur=sum(
            trade.pnl_eur or 0.0 for trade in trades
        ),
        open_trade=state.open_trade,
        recent_trades=trades[-RECENT_TRADES_LIMIT:][::-1],
    )
