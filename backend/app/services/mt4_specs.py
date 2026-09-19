import csv
import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.broker import BrokerSymbolSpec


def _build_spec(
    symbol: str,
    *,
    bid: object,
    ask: object,
    tick_size: object,
    tick_value: object,
    min_lot: object,
    max_lot: object,
    lot_step: object,
    margin_required: object,
) -> BrokerSymbolSpec | None:
    try:
        return BrokerSymbolSpec(
            symbol=symbol.upper(),
            bid=float(bid),
            ask=float(ask),
            tick_size=float(tick_size),
            tick_value=float(tick_value),
            min_lot=float(min_lot),
            max_lot=float(max_lot),
            lot_step=float(lot_step),
            margin_required=float(margin_required),
        )
    except (TypeError, ValueError, ValidationError):
        return None


def read_symbol_snapshot(path: Path) -> dict[str, BrokerSymbolSpec]:
    if not path.is_file():
        return {}

    specs: dict[str, BrokerSymbolSpec] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            spec = _build_spec(
                symbol,
                bid=row.get("bid"),
                ask=row.get("ask"),
                tick_size=row.get("tick_size"),
                tick_value=row.get("tick_value"),
                min_lot=row.get("min_lot"),
                max_lot=row.get("max_lot"),
                lot_step=row.get("lot_step"),
                margin_required=row.get("margin_required") or 0,
            )
            if spec is not None:
                specs[symbol] = spec
    return specs


def read_symbol_json(path: Path) -> BrokerSymbolSpec | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        symbol_spec = payload["symbol_spec"]
        return _build_spec(
            str(payload["symbol"]),
            bid=payload["bid"],
            ask=payload["ask"],
            tick_size=symbol_spec["tick_size"],
            tick_value=symbol_spec["tick_value"],
            min_lot=symbol_spec["min_lot"],
            max_lot=symbol_spec["max_lot"],
            lot_step=symbol_spec["lot_step"],
            margin_required=symbol_spec.get("margin_required", 0),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def list_mt4_symbol_specs(files_dir: Path) -> dict[str, BrokerSymbolSpec]:
    specs = read_symbol_snapshot(files_dir / "trading_symbol_specs.csv")
    for path in files_dir.glob("mt4_data_*.json"):
        spec = read_symbol_json(path)
        if spec is not None:
            specs.setdefault(spec.symbol.upper(), spec)
    return specs


def get_mt4_symbol_spec(files_dir: Path, symbol: str) -> BrokerSymbolSpec | None:
    return list_mt4_symbol_specs(files_dir).get(symbol.upper())
