"""Broker-session readiness profiles, evaluated in the MT4 server timezone."""

from datetime import datetime
from enum import StrEnum

from app.services.mt4_csv import _server_timezone


class MarketSessionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


# The MT4 export has no per-symbol session metadata.  This operational profile
# records the observed broker behaviour: BTC quotes/M5 continue on weekends,
# while FX and metals stop after Friday and resume in the broker workweek.
# Keep profiles here, rather than scattering weekday checks through preflight,
# so broker-provided metadata can replace them per symbol later.
_ALWAYS_OPEN = {"BTCUSD"}
_WEEKDAY_SESSION = {"EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"}


def market_session_status(symbol: str, now: datetime) -> MarketSessionStatus:
    """Return the expected broker session status for an aware server datetime."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("market session evaluation requires a timezone-aware now")
    local_now = now.astimezone(_server_timezone())
    normalized = symbol.upper()
    if normalized in _ALWAYS_OPEN:
        return MarketSessionStatus.OPEN
    if normalized in _WEEKDAY_SESSION:
        return (
            MarketSessionStatus.OPEN
            if local_now.weekday() < 5
            else MarketSessionStatus.CLOSED
        )
    return MarketSessionStatus.UNKNOWN
