import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain.broker import BrokerSymbolSpec


class ResearchSymbolExecution(BaseModel):
    spread: float = Field(gt=0)
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    min_lot: float = Field(gt=0)
    max_lot: float = Field(gt=0)
    lot_step: float = Field(gt=0)
    margin_required: float = Field(ge=0)
    spread_observations: int = Field(ge=1)


class ResearchExecutionProfile(BaseModel):
    version: str
    observed_through: str
    source: str
    symbols: dict[str, ResearchSymbolExecution]


def load_research_execution_profile(
    path: Path,
) -> ResearchExecutionProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ResearchExecutionProfile.model_validate(payload)


def apply_research_execution_profile(
    spec: BrokerSymbolSpec,
    profile: ResearchExecutionProfile,
) -> BrokerSymbolSpec:
    frozen = profile.symbols.get(spec.symbol.upper())
    if frozen is None:
        return spec

    return spec.model_copy(
        update={
            "ask": spec.bid + frozen.spread,
            "tick_size": frozen.tick_size,
            "tick_value": frozen.tick_value,
            "min_lot": frozen.min_lot,
            "max_lot": frozen.max_lot,
            "lot_step": frozen.lot_step,
            "margin_required": frozen.margin_required,
        }
    )


def apply_research_execution_profile_to_specs(
    specs: dict[str, BrokerSymbolSpec],
    profile: ResearchExecutionProfile,
) -> dict[str, BrokerSymbolSpec]:
    return {
        symbol: apply_research_execution_profile(spec, profile)
        for symbol, spec in specs.items()
    }
