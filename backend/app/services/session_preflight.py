from datetime import datetime
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


WORKER_STALE_SECONDS = 180


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

    assets: list[SessionAssetStatus] = []
    for symbol in watch_symbols:
        normalized = symbol.upper()
        asset = by_symbol.get(normalized)
        if asset is None:
            continue
        state = _asset_state(asset)
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
                reason=asset.reason,
            )
        )

    ready = [item.symbol for item in assets if item.state == SessionAssetState.READY]
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
    elif non_btc_ready:
        status = SessionReadinessStatus.READY
        reason = (
            "session runtime is healthy; paper-ready markets: "
            + ", ".join(ready)
        )
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
        waiting_symbols=waiting,
        degraded_symbols=degraded,
        assets=assets,
        reason=reason,
    )


def _asset_state(asset) -> SessionAssetState:
    if not asset.has_m5 or not asset.has_m15:
        return SessionAssetState.MISSING_HISTORY
    if not asset.broker_spec_ready:
        return SessionAssetState.MISSING_SPEC
    if not asset.quote_live:
        return SessionAssetState.WAITING_QUOTE
    return SessionAssetState.READY
