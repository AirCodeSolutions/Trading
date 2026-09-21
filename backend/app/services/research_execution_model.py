import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain.broker import BrokerSymbolSpec


class ResearchSpreadProxy(BaseModel):
    spread: float = Field(gt=0)
    samples: int = Field(ge=1)


class ResearchExecutionModel(BaseModel):
    version: str = Field(min_length=1)
    as_of: datetime
    method: str = Field(min_length=1)
    symbols: dict[str, ResearchSpreadProxy]


def load_research_execution_model(path: Path) -> ResearchExecutionModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = ResearchExecutionModel.model_validate(payload)
    if model.as_of.utcoffset() is None:
        raise ValueError("research execution model as_of must be timezone-aware")
    return model


def apply_research_execution_model(
    spec: BrokerSymbolSpec,
    model: ResearchExecutionModel,
) -> BrokerSymbolSpec:
    proxy = model.symbols.get(spec.symbol.upper())
    if proxy is None:
        raise ValueError(
            f"research spread proxy missing for {spec.symbol.upper()}"
        )
    return spec.model_copy(
        update={
            "ask": spec.bid + proxy.spread,
        }
    )
