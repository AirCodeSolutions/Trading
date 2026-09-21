import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.broker import BrokerSymbolSpec


def load_research_broker_specs(
    path: Path,
) -> dict[str, BrokerSymbolSpec]:
    if not path.is_file():
        raise FileNotFoundError(f"research broker spec file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["specs"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid research broker spec payload") from exc

    if not isinstance(rows, list):
        raise ValueError("research broker specs must be a list")

    specs: dict[str, BrokerSymbolSpec] = {}
    for row in rows:
        try:
            spec = BrokerSymbolSpec.model_validate(row)
        except ValidationError as exc:
            raise ValueError("invalid research broker symbol spec") from exc
        symbol = spec.symbol.upper()
        if symbol in specs:
            raise ValueError(f"duplicate research broker spec: {symbol}")
        specs[symbol] = spec
    return specs


def get_research_broker_spec(
    path: Path,
    symbol: str,
) -> BrokerSymbolSpec | None:
    return load_research_broker_specs(path).get(symbol.upper())
