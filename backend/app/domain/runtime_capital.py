from enum import StrEnum

from pydantic import BaseModel, Field


class RuntimeCapitalSource(StrEnum):
    BROKER_EQUITY = "broker_equity"
    BROKER_BALANCE = "broker_balance"
    RESEARCH_FALLBACK = "research_fallback"
    UNAVAILABLE = "unavailable"


class RuntimeCapitalSnapshot(BaseModel):
    capital_eur: float | None = Field(default=None, gt=0)
    source: RuntimeCapitalSource
    is_demo: bool | None = None
