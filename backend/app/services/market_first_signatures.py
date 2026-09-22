from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from app.domain.market import MarketBar, Timeframe
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path

ATHENS = ZoneInfo("Europe/Athens")

MARKET_MOVE_THRESHOLD_ATR = 1.5
MARKET_MOVE_HORIZON_BARS = 12

ARCHETYPES = {
    "continuation_extreme": lambda row: row["aligned_position_24"] >= 0.80
    and row["aligned_return_6_atr"] > 0,
    "opposite_extreme_reversal": lambda row: row["aligned_position_24"] <= 0.20
    and row["aligned_return_6_atr"] < 0,
    "compressed": lambda row: row["compression_6_24"] <= 0.35,
    "high_volatility": lambda row: row["atr_ratio_96"] >= 1.25,
    "early_displacement": lambda row: row["aligned_return_3_atr"] >= 0.50,
}


def analyze_market_first_signatures(
    files_dir: Path,
    symbol: str,
    *,
    train_end: datetime,
    validation_end: datetime,
    move_threshold_atr: float = MARKET_MOVE_THRESHOLD_ATR,
    horizon_bars: int = MARKET_MOVE_HORIZON_BARS,
) -> dict:
    bars = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    rows = build_market_first_signature_rows(
        bars,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
    )
    return {
        "symbol": symbol,
        "move_threshold_atr": move_threshold_atr,
        "horizon_bars": horizon_bars,
        "episodes": len(rows),
        "splits": {
            "train": summarize_signature_rows(
                [row for row in rows if row["birth_at"] < train_end]
            ),
            "validation": summarize_signature_rows(
                [
                    row
                    for row in rows
                    if train_end <= row["birth_at"] < validation_end
                ]
            ),
            "holdout": summarize_signature_rows(
                [row for row in rows if row["birth_at"] >= validation_end]
            ),
        },
    }


def build_market_first_signature_rows(
    bars: list[MarketBar],
    *,
    move_threshold_atr: float = MARKET_MOVE_THRESHOLD_ATR,
    horizon_bars: int = MARKET_MOVE_HORIZON_BARS,
) -> list[dict]:
    if len(bars) < 64 + horizon_bars:
        return []

    atr = _atr_series(bars)
    rows: list[dict] = []
    index = 48
    last = len(bars) - horizon_bars - 1

    while index <= last:
        bar = bars[index]
        current_atr = atr[index]
        if current_atr <= 0:
            index += 1
            continue

        future = bars[index + 1 : index + 1 + horizon_bars]
        up_move = max(item.high for item in future) - bar.close
        down_move = bar.close - min(item.low for item in future)
        up_atr = max(0.0, up_move / current_atr)
        down_atr = max(0.0, down_move / current_atr)
        move_atr = max(up_atr, down_atr)
        if move_atr < move_threshold_atr:
            index += 1
            continue

        direction = 1 if up_atr >= down_atr else -1
        range_24 = bars[index - 23 : index + 1]
        range_48 = bars[index - 47 : index + 1]

        low_24 = min(item.low for item in range_24)
        high_24 = max(item.high for item in range_24)
        low_48 = min(item.low for item in range_48)
        high_48 = max(item.high for item in range_48)

        position_24 = _position(bar.close, low_24, high_24)
        position_48 = _position(bar.close, low_48, high_48)
        aligned_position_24 = (
            position_24 if direction > 0 else 1.0 - position_24
        )
        aligned_position_48 = (
            position_48 if direction > 0 else 1.0 - position_48
        )

        range_6 = bars[index - 5 : index + 1]
        range_6_width = max(item.high for item in range_6) - min(
            item.low for item in range_6
        )
        range_24_width = high_24 - low_24
        compression = (
            range_6_width / range_24_width if range_24_width > 0 else 1.0
        )

        atr_window = atr[max(0, index - 95) : index + 1]
        atr_med = median(atr_window) if atr_window else current_atr

        candle_range = bar.high - bar.low
        body_aligned = (
            direction * (bar.close - bar.open) / candle_range
            if candle_range > 0
            else 0.0
        )

        row = {
            "birth_at": bar.timestamp + timedelta(minutes=5),
            "direction": direction,
            "move_atr": move_atr,
            "aligned_return_3_atr": direction
            * (bar.close - bars[index - 3].close)
            / current_atr,
            "aligned_return_6_atr": direction
            * (bar.close - bars[index - 6].close)
            / current_atr,
            "aligned_return_12_atr": direction
            * (bar.close - bars[index - 12].close)
            / current_atr,
            "aligned_position_24": aligned_position_24,
            "aligned_position_48": aligned_position_48,
            "compression_6_24": compression,
            "atr_ratio_96": current_atr / atr_med if atr_med > 0 else 1.0,
            "body_alignment": body_aligned,
            "hour_athens": (
                bar.timestamp + timedelta(minutes=5)
            ).astimezone(ATHENS).hour,
        }
        rows.append(row)
        index += horizon_bars

    return rows


def summarize_signature_rows(rows: list[dict]) -> dict:
    features = (
        "move_atr",
        "aligned_return_3_atr",
        "aligned_return_6_atr",
        "aligned_return_12_atr",
        "aligned_position_24",
        "aligned_position_48",
        "compression_6_24",
        "atr_ratio_96",
        "body_alignment",
    )
    summary = {
        "episodes": len(rows),
        "features": {},
        "archetypes": {},
        "top_hours": [],
    }
    if not rows:
        return summary

    for feature in features:
        values = sorted(float(row[feature]) for row in rows)
        summary["features"][feature] = {
            "median": median(values),
            "q25": _quantile(values, 0.25),
            "q75": _quantile(values, 0.75),
        }

    for name, predicate in ARCHETYPES.items():
        count = sum(bool(predicate(row)) for row in rows)
        summary["archetypes"][name] = {
            "count": count,
            "share": count / len(rows),
        }

    hours: dict[int, int] = {}
    for row in rows:
        hour = int(row["hour_athens"])
        hours[hour] = hours.get(hour, 0) + 1
    summary["top_hours"] = sorted(
        ({"hour": hour, "count": count} for hour, count in hours.items()),
        key=lambda item: (-item["count"], item["hour"]),
    )[:8]
    return summary


def _atr_series(bars: list[MarketBar], period: int = 14) -> list[float]:
    values: list[float] = []
    output: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        values.append(true_range)
        previous_close = bar.close
        window = values[max(0, len(values) - period) :]
        output.append(sum(window) / len(window))
    return output


def _position(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.5
    return (value - low) / (high - low)


def _quantile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    index = round((len(values) - 1) * quantile)
    return values[index]
