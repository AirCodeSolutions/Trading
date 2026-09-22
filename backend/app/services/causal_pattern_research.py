from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from app.domain.causal_pattern_research import (
    AssetCausalPatternResearch,
    CausalPatternHistoricalSummary,
    CausalPatternResearchReport,
    CausalPatternSplitSummary,
)
from app.domain.market import MarketBar, Timeframe
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.mt4_csv import read_mt4_csv
from app.services.mt4_history import resolve_mt4_history_path
from app.services.trading_intelligence import _atr_series, _classify_causal_context

DEFAULT_MOVE_THRESHOLD_ATR = 1.5
DEFAULT_HORIZON_BARS = 12


def build_causal_pattern_research_report(
    files_dir: Path,
    symbols: tuple[str, ...],
    *,
    generated_at: datetime,
    train_end: datetime,
    validation_end: datetime,
    move_threshold_atr: float = DEFAULT_MOVE_THRESHOLD_ATR,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
) -> CausalPatternResearchReport:
    if train_end >= validation_end:
        raise ValueError("train_end must be earlier than validation_end")
    if move_threshold_atr <= 0:
        raise ValueError("move_threshold_atr must be positive")
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be positive")

    assets = [
        analyze_asset_causal_patterns(
            files_dir,
            symbol,
            train_end=train_end,
            validation_end=validation_end,
            move_threshold_atr=move_threshold_atr,
            horizon_bars=horizon_bars,
        )
        for symbol in symbols
    ]
    return CausalPatternResearchReport(
        generated_at=generated_at,
        train_end=train_end,
        validation_end=validation_end,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
        assets=assets,
    )


def analyze_asset_causal_patterns(
    files_dir: Path,
    symbol: str,
    *,
    train_end: datetime,
    validation_end: datetime,
    move_threshold_atr: float = DEFAULT_MOVE_THRESHOLD_ATR,
    horizon_bars: int = DEFAULT_HORIZON_BARS,
) -> AssetCausalPatternResearch:
    bars = read_mt4_csv(
        resolve_mt4_history_path(files_dir, symbol, Timeframe.M5),
        symbol,
        Timeframe.M5,
    )
    atr = _atr_series(bars)
    rows = _historical_causal_episodes(
        bars=bars,
        atr=atr,
        move_threshold_atr=move_threshold_atr,
        horizon_bars=horizon_bars,
    )

    by_pattern: dict[OpportunityCausalPattern, list[dict]] = defaultdict(list)
    for row in rows:
        by_pattern[row["context"].pattern].append(row)

    patterns = []
    for pattern in OpportunityCausalPattern:
        pattern_rows = by_pattern.get(pattern, [])
        patterns.append(
            CausalPatternHistoricalSummary(
                pattern=pattern,
                train=_split_summary(
                    [row for row in pattern_rows if row["birth_at"] < train_end]
                ),
                validation=_split_summary(
                    [
                        row
                        for row in pattern_rows
                        if train_end <= row["birth_at"] < validation_end
                    ]
                ),
                holdout=_split_summary(
                    [
                        row
                        for row in pattern_rows
                        if row["birth_at"] >= validation_end
                    ]
                ),
            )
        )

    return AssetCausalPatternResearch(
        symbol=symbol,
        total_episodes=len(rows),
        patterns=patterns,
    )


def _historical_causal_episodes(
    *,
    bars: list[MarketBar],
    atr: list[float],
    move_threshold_atr: float,
    horizon_bars: int,
) -> list[dict]:
    if len(bars) < 24 + horizon_bars + 1:
        return []

    rows: list[dict] = []
    index = 24
    last_index = len(bars) - horizon_bars - 1

    while index <= last_index:
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

        episode_side = Side.BUY if up_atr >= down_atr else Side.SELL
        context = _classify_causal_context(
            bars=bars,
            atr=atr,
            index=index,
            episode_side=episode_side,
        )
        rows.append(
            {
                "birth_at": bar.timestamp + timedelta(minutes=5),
                "move_atr": move_atr,
                "episode_side": episode_side,
                "context": context,
            }
        )
        index += horizon_bars

    return rows


def _split_summary(rows: list[dict]) -> CausalPatternSplitSummary:
    if not rows:
        return CausalPatternSplitSummary(
            episodes=0,
            directional_episodes=0,
            aligned=0,
            opposed=0,
            no_direction=0,
            alignment_rate=None,
            average_move_atr=0.0,
        )

    aligned = sum(
        row["context"].aligned_with_move is True
        for row in rows
    )
    opposed = sum(
        row["context"].aligned_with_move is False
        for row in rows
    )
    no_direction = sum(
        row["context"].aligned_with_move is None
        for row in rows
    )
    directional = aligned + opposed
    return CausalPatternSplitSummary(
        episodes=len(rows),
        directional_episodes=directional,
        aligned=aligned,
        opposed=opposed,
        no_direction=no_direction,
        alignment_rate=(aligned / directional) if directional else None,
        average_move_atr=fmean(float(row["move_atr"]) for row in rows),
    )
