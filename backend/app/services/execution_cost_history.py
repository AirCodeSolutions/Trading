import json
from datetime import datetime
from pathlib import Path

from app.services.mt4_live_quotes import read_live_market_quotes


def collect_execution_cost_snapshot(
    files_dir: Path,
    ledger_path: Path,
    now: datetime,
    symbols: tuple[str, ...] | None = None,
) -> int:
    quotes = read_live_market_quotes(files_dir, now, symbols=symbols)
    if not quotes:
        return 0

    previous_quote_at = _latest_quote_at_by_symbol(ledger_path)
    appended = 0
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    with ledger_path.open("a", encoding="utf-8") as handle:
        for quote in quotes:
            quote_at = quote.as_of.isoformat()
            if previous_quote_at.get(quote.symbol) == quote_at:
                continue
            record = {
                "observed_at": now.isoformat(),
                "symbol": quote.symbol,
                "quote_at": quote.as_of.isoformat(),
                "bid": quote.bid,
                "ask": quote.ask,
                "spread": quote.spread,
                "spread_pct": quote.spread_pct,
                "status": quote.status.value,
            }
            handle.write(json.dumps(record, separators=(",", ":")))
            handle.write("\n")
            appended += 1
    return appended


def summarize_execution_costs(
    ledger_path: Path,
    *,
    limit: int = 2000,
) -> dict[str, dict[str, float | int]]:
    records = _tail_records(ledger_path, limit)
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        symbol = str(record.get("symbol", ""))
        if symbol:
            grouped.setdefault(symbol, []).append(record)

    result: dict[str, dict[str, float | int]] = {}
    for symbol, values in grouped.items():
        spreads = [float(item["spread"]) for item in values if "spread" in item]
        spread_pcts = [
            float(item["spread_pct"]) for item in values if "spread_pct" in item
        ]
        if not spreads:
            continue
        result[symbol] = {
            "samples": len(spreads),
            "average_spread": sum(spreads) / len(spreads),
            "max_spread": max(spreads),
            "average_spread_pct": (
                sum(spread_pcts) / len(spread_pcts) if spread_pcts else 0.0
            ),
        }
    return result


def _latest_quote_at_by_symbol(path: Path) -> dict[str, str]:
    latest: dict[str, str] = {}
    for record in _tail_records(path, 500):
        symbol = str(record.get("symbol", ""))
        quote_at = str(record.get("quote_at", ""))
        if symbol and quote_at:
            latest[symbol] = quote_at
    return latest


def _tail_records(path: Path, limit: int) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records[-limit:]
