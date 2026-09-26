from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.domain.macro import MacroGateStatus
from app.domain.portfolio import TradingOverview
from app.domain.session import (
    SessionAssetState,
    SessionAssetStatus,
    SessionAssetTimeline,
    SessionPreflight,
    SessionReadinessStatus,
    SessionRuntimeState,
    SessionRuntimeSymbolState,
    ShadowWorkerHeartbeat,
)
from app.services.market_session import MarketSessionStatus, market_session_status
from app.services.market_universe import build_market_universe
from app.services.mt4_live_quotes import LiveMarketQuote, read_live_market_quotes

WORKER_STALE_SECONDS = 180
M5_SYNC_MAX_AGE = timedelta(minutes=10)
M5_STALL_AFTER = timedelta(minutes=20)


def load_worker_heartbeat(path: Path) -> ShadowWorkerHeartbeat | None:
    if not path.is_file():
        return None
    try:
        return ShadowWorkerHeartbeat.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def load_session_runtime_state(path: Path) -> SessionRuntimeState:
    if not path.is_file():
        return SessionRuntimeState()
    try:
        return SessionRuntimeState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return SessionRuntimeState()


def save_session_runtime_state(path: Path, state: SessionRuntimeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
    universe = build_market_universe(files_dir, now, symbols=watch_symbols)
    by_symbol = {item.symbol.upper(): item for item in universe}
    quotes = {
        quote.symbol.upper(): quote
        for quote in read_live_market_quotes(files_dir, now, symbols=watch_symbols)
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
    state_path = runtime_dir / "session_state.json"
    runtime_state = load_session_runtime_state(state_path)

    assets: list[SessionAssetStatus] = []
    timeline: list[SessionAssetTimeline] = []
    for symbol in watch_symbols:
        normalized = symbol.upper()
        asset = by_symbol.get(normalized)
        if asset is None:
            continue
        market_session = market_session_status(normalized, now)
        quote = quotes.get(normalized)
        symbol_state = runtime_state.symbols.get(
            normalized,
            SessionRuntimeSymbolState(),
        )

        if asset.quote_live:
            if symbol_state.quote_live_since is None:
                symbol_state = SessionRuntimeSymbolState(
                    quote_live_since=now,
                )
        else:
            symbol_state = SessionRuntimeSymbolState()

        market_closed = market_session == MarketSessionStatus.CLOSED
        waiting_for_closed_m5 = (
            not market_closed
            and
            asset.quote_live
            and _waiting_for_fresh_closed_m5(quote, now)
        )
        if (
            asset.quote_live
            and not waiting_for_closed_m5
            and symbol_state.first_fresh_m5_at is None
        ):
            symbol_state.first_fresh_m5_at = now

        m5_stalled = bool(
            waiting_for_closed_m5
            and symbol_state.quote_live_since is not None
            and now - symbol_state.quote_live_since > M5_STALL_AFTER
        )
        if m5_stalled and symbol_state.m5_stalled_at is None:
            symbol_state.m5_stalled_at = now

        worker_warming = normalized in warming_from_worker
        warming_up = worker_warming or (
            waiting_for_closed_m5 and not m5_stalled
        )
        asset_state = _asset_state(
            asset,
            market_session=market_session,
            warming_up=warming_up,
            m5_stalled=m5_stalled,
        )
        if (
            asset_state == SessionAssetState.READY
            and symbol_state.ready_at is None
        ):
            symbol_state.ready_at = now

        runtime_state.symbols[normalized] = symbol_state
        last_closed_m5_at = (
            quote.last_closed_m5_at
            if quote is not None
            else None
        )
        timeline.append(
            SessionAssetTimeline(
                symbol=normalized,
                quote_live_since=symbol_state.quote_live_since,
                first_fresh_m5_at=symbol_state.first_fresh_m5_at,
                ready_at=symbol_state.ready_at,
                m5_stalled_at=symbol_state.m5_stalled_at,
                last_closed_m5_at=last_closed_m5_at,
            )
        )

        if market_closed:
            asset_reason = "market closed for the configured broker weekly session"
        elif market_session == MarketSessionStatus.UNKNOWN:
            asset_reason = "market session is unknown; readiness remains conservative"
        elif m5_stalled:
            asset_reason = (
                "broker quote is live but closed M5 feed is stalled "
                "for more than 20 minutes"
            )
        elif waiting_for_closed_m5:
            asset_reason = (
                "live broker quote received; waiting for a fresh closed M5 bar"
            )
        elif worker_warming:
            asset_reason = (
                "session reopen warmup: waiting for three complete M5 bars"
            )
        else:
            asset_reason = asset.reason

        assets.append(
            SessionAssetStatus(
                symbol=normalized,
                state=asset_state,
                market_session=market_session.value,
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

    save_session_runtime_state(state_path, runtime_state)

    ready = [
        item.symbol for item in assets if item.state == SessionAssetState.READY
    ]
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
    closed = [
        item.symbol
        for item in assets
        if item.state == SessionAssetState.MARKET_CLOSED
    ]
    degraded = [
        item.symbol
        for item in assets
        if item.state
        in {
            SessionAssetState.M5_STALLED,
            SessionAssetState.MISSING_SPEC,
            SessionAssetState.MISSING_HISTORY,
        }
    ]

    non_btc_ready = [symbol for symbol in ready if symbol != "BTCUSD"]
    non_btc_warming = [symbol for symbol in warming if symbol != "BTCUSD"]
    live_but_degraded = [
        item.symbol
        for item in assets
        if item.quote_live
        and item.state
        in {
            SessionAssetState.M5_STALLED,
            SessionAssetState.MISSING_SPEC,
            SessionAssetState.MISSING_HISTORY,
        }
    ]
    unknown_session = [
        item.symbol
        for item in assets
        if item.state == SessionAssetState.UNKNOWN_SESSION
    ]

    if not worker_ok:
        status = SessionReadinessStatus.BLOCKED
        reason = "SHADOW worker heartbeat is missing, failed or stale"
    elif live_but_degraded:
        status = SessionReadinessStatus.DEGRADED
        reason = (
            "open-market data is live but incomplete or stalled for: "
            + ", ".join(live_but_degraded)
        )
    elif non_btc_warming and not non_btc_ready:
        status = SessionReadinessStatus.WARMING_UP
        reason = (
            "market reopened; waiting for closed M5 synchronization/warmup: "
            + ", ".join(non_btc_warming)
        )
    elif unknown_session:
        status = SessionReadinessStatus.DEGRADED
        reason = "market session is unknown for: " + ", ".join(unknown_session)
    elif ready:
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
        closed_symbols=closed,
        degraded_symbols=degraded,
        assets=assets,
        timeline=timeline,
        reason=reason,
    )


def _asset_state(
    asset,
    *,
    market_session: MarketSessionStatus,
    warming_up: bool,
    m5_stalled: bool,
) -> SessionAssetState:
    if market_session == MarketSessionStatus.CLOSED:
        return SessionAssetState.MARKET_CLOSED
    if market_session == MarketSessionStatus.UNKNOWN:
        return SessionAssetState.UNKNOWN_SESSION
    if not asset.has_m5 or not asset.has_m15:
        return SessionAssetState.MISSING_HISTORY
    if not asset.broker_spec_ready:
        return SessionAssetState.MISSING_SPEC
    if not asset.quote_live:
        return SessionAssetState.WAITING_QUOTE
    if m5_stalled:
        return SessionAssetState.M5_STALLED
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
