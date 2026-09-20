from datetime import datetime, timedelta
from pathlib import Path

from app.domain.macro import MacroGateStatus
from app.domain.portfolio import TradingOverview
from app.domain.session import (
    SessionAssetState,
    SessionAssetStatus,
    SessionPreflight,
    SessionReadinessStatus,
    ShadowWorkerHeartbeat,
)
from app.services.market_universe import build_market_universe
from app.services.mt4_live_quotes import LiveMarketQuote, read_live_market_quotes

WORKER_STALE_SECONDS = 180
M5_SYNC_MAX_AGE = timedelta(minutes=10)


def load_worker_heartbeat(path: Path) -> ShadowWorkerHeartbeat | None:
    if not path.is_file():
        return None
    try:
        return ShadowWorkerHeartbeat.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def build_session_preflight(
    *,
    files_dir: Path,
    runtime_dir: Path,
    now: datetime,
    macro: MacroGateStatus,
    overview: TradingOverview,
    demo_execution_ready: bool,
    watch_symbols: tuple[str, ...],
) -> SessionPreflight:
    universe = build_market_universe(files_dir, now)
    by_symbol = {item.symbol.upper(): item for item in universe}
    quotes = {
        quote.symbol.upper(): quote
        for quote in read_live_market_quotes(files_dir, now)
    }
    heartbeat = load_worker_heartbeat(runtime_dir / "worker_heartbeat.json")
    worker_age = (
        max(0.0, (now - heartbeat.at).total_seconds())
        if heartbeat is not None
        else None
    )
    worker_ok = bool(
        heartbeat is not None
        and heartbeat.ok
        and worker_age is not None
        and worker_age <= WORKER_STALE_SECONDS
    )

    warming_from_worker = (
        set(heartbeat.warming_up_symbols)
        if heartbeat is not None
        else set()
    )

    assets: list[SessionAssetStatus] = []
    for symbol in watch_symbols:
        normalized = symbol.upper()
        asset = by_symbol.get(normalized)
        if asset is None:
            continue
        quote = quotes.get(normalized)
        waiting_for_closed_m5 = (
            asset.quote_live
            and _waiting_for_fresh_closed_m5(quote, now)
        )
        warming_up = (
            normalized in warming_from_worker
            or waiting_for_closed_m5
        )
        state = _asset_state(
            asset,
            warming_up=warming_up,
        )
        if waiting_for_closed_m5:
            asset_reason = (
                "live broker quote received; waiting for a fresh closed M5 bar"
            )
        elif normalized in warming_from_worker:
            asset_reason = (
                "session reopen warmup: waiting for three complete M5 bars"
            )
        else:
            asset_reason = asset.reason

        assets.append(
            SessionAssetStatus(
                symbol=normalized,
                state=state,
                quote_live=asset.quote_live,
                paper_ready=asset.paper_ready,
                broker_spec_ready=asset.broker_spec_ready,
                has_m5=asset.has_m5,
                has_m15=asset.has_m15,
                price=asset.price,
                as_of=asset.as_of,
                reason=asset_reason,
            )
        )

    ready = [item.symbol for item in assets if item.state == SessionAssetState.READY]
    warming = [
        item.symbol
        for item in assets
        if item.state == SessionAssetState.WARMING_UP
    ]
    waiting = [
        item.symbol
        for item in assets
        if item.state == SessionAssetState.WAITING_QUOTE
    ]
    degraded = [
        item.symbol
        for item in assets
        if item.state
        in {SessionAssetState.MISSING_SPEC, SessionAssetState.MISSING_HISTORY}
    ]

    non_btc_ready = [symbol for symbol in ready if symbol != "BTCUSD"]
    non_btc_warming = [symbol for symbol in warming if symbol != "BTCUSD"]
    live_but_degraded = [
        item.symbol
        for item in assets
        if item.quote_live
        and item.state
        in {SessionAssetState.MISSING_SPEC, SessionAssetState.MISSING_HISTORY}
    ]

    if not worker_ok:
        status = SessionReadinessStatus.BLOCKED
        reason = "SHADOW worker heartbeat is missing, failed or stale"
    elif live_but_degraded:
        status = SessionReadinessStatus.DEGRADED
        reason = (
            "open-market data is live but incomplete for: "
            + ", ".join(live_but_degraded)
        )
    elif non_btc_warming and not non_btc_ready:
        status = SessionReadinessStatus.WARMING_UP
        reason = (
            "market reopened; waiting for three complete M5 bars: "
            + ", ".join(non_btc_warming)
        )
    elif non_btc_ready:
        status = SessionReadinessStatus.READY
        reason = (
            "session runtime is healthy; paper-ready markets: "
            + ", ".join(ready)
        )
        if warming:
            reason += "; warming: " + ", ".join(warming)
    else:
        status = SessionReadinessStatus.WAITING_MARKET
        reason = (
            "runtime is healthy and waiting for non-BTC broker quotes "
            "to become live"
        )

    if macro.blocked and status == SessionReadinessStatus.READY:
        reason += "; macro gate currently blocks new execution"

    return SessionPreflight(
        at=now,
        status=status,
        worker_ok=worker_ok,
        worker_age_seconds=worker_age,
        macro_blocked=macro.blocked,
        portfolio_action=overview.portfolio.action.value,
        demo_execution_ready=demo_execution_ready,
        ready_symbols=ready,
        warming_symbols=warming,
        waiting_symbols=waiting,
        degraded_symbols=degraded,
        assets=assets,
        reason=reason,
    )


def _asset_state(
    asset,
    *,
    warming_up: bool,
) -> SessionAssetState:
    if not asset.has_m5 or not asset.has_m15:
        return SessionAssetState.MISSING_HISTORY
    if not asset.broker_spec_ready:
        return SessionAssetState.MISSING_SPEC
    if not asset.quote_live:
        return SessionAssetState.WAITING_QUOTE
    if warming_up:
        return SessionAssetState.WARMING_UP
    return SessionAssetState.READY


def _waiting_for_fresh_closed_m5(
    quote: LiveMarketQuote | None,
    now: datetime,
) -> bool:
    if quote is None or quote.last_closed_m5_at is None:
        return True
    last_close_at = quote.last_closed_m5_at + timedelta(minutes=5)
    return now - last_close_at > M5_SYNC_MAX_AGE
