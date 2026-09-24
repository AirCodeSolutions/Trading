from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.market import MarketBar, Timeframe
from app.domain.trading_intelligence import (
    MarketOpportunityEpisode,
    OpportunityCausalPattern,
    OpportunityDetectionStage,
    TradingIntelligenceOverview,
)
from app.domain.xau_microbar import (
    XauMicrobarM1,
    XauUnseenTransitionSnapshot,
)
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.trading_intelligence import _atr_series
from app.services.unclassified_transition_research import first_directional_transition
from app.services.xau_microbar import (
    SUPPORTED_SYMBOLS,
    _geometry_window,
    load_xau_microbars,
    microbar_ledger_file,
)

SYMBOL = "XAUUSD"
RECENT_M5_LIMIT = 512


def unseen_transition_file(symbol: str) -> str:
    return f"{symbol.upper()}_unseen_m1_transitions.jsonl"


UNSEEN_TRANSITION_FILE = unseen_transition_file(SYMBOL)


def load_unseen_transition_snapshots(
    path: Path,
) -> list[XauUnseenTransitionSnapshot]:
    if not path.is_file():
        return []
    rows: list[XauUnseenTransitionSnapshot] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(
                    XauUnseenTransitionSnapshot.model_validate(json.loads(line))
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return rows


def load_xau_unseen_transition_snapshots(
    path: Path,
) -> list[XauUnseenTransitionSnapshot]:
    return load_unseen_transition_snapshots(path)


def append_unseen_transition_snapshot(
    path: Path,
    snapshot: XauUnseenTransitionSnapshot,
) -> bool:
    existing = load_unseen_transition_snapshots(path)
    if any(row.episode_id == snapshot.episode_id for row in existing):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(snapshot.model_dump_json())
        handle.write("\n")
    return True


def append_xau_unseen_transition_snapshot(
    path: Path,
    snapshot: XauUnseenTransitionSnapshot,
) -> bool:
    return append_unseen_transition_snapshot(path, snapshot)


def build_unseen_transition_snapshot(
    episode: MarketOpportunityEpisode,
    bars: list[MarketBar],
    atr: list[float],
    microbars: list[XauMicrobarM1],
    *,
    symbol: str,
) -> XauUnseenTransitionSnapshot | None:
    normalized = symbol.upper()
    if episode.symbol.upper() != normalized:
        return None
    if episode.detection_stage != OpportunityDetectionStage.UNSEEN:
        return None
    if episode.causal_context.pattern != OpportunityCausalPattern.UNCLASSIFIED:
        return None

    birth_index = next(
        (
            index
            for index, bar in enumerate(bars)
            if bar.timestamp + timedelta(minutes=5) == episode.birth_at
        ),
        None,
    )
    if birth_index is None or birth_index >= len(atr):
        return None

    causal_microbars = [
        row
        for row in microbars
        if row.minute_at + timedelta(minutes=1) <= episode.birth_at
    ]
    geometry_5m = _geometry_window(causal_microbars, 5)
    if geometry_5m is None or geometry_5m.bars < 5:
        return None
    geometry_15m = _geometry_window(causal_microbars, 15)
    latest_microbar_at = causal_microbars[-1].minute_at

    transition = first_directional_transition(
        bars,
        atr,
        birth_index,
        episode_side=episode.side,
        max_wait_bars=3,
    )
    transition_pattern = None
    transition_side = None
    transition_at = None
    transition_bars_waited = None
    transition_aligned = None
    move_consumed_atr = None

    if transition is not None:
        transition_index, context = transition
        transition_pattern = context.pattern
        transition_side = context.side
        transition_at = bars[transition_index].timestamp + timedelta(minutes=5)
        transition_bars_waited = transition_index - birth_index
        transition_aligned = context.side == episode.side
        entry_index = transition_index + 1
        if entry_index < len(bars) and episode.atr_m5 > 0:
            entry = bars[entry_index].open
            raw_move = (
                entry - episode.reference_price
                if episode.side.value == "buy"
                else episode.reference_price - entry
            )
            move_consumed_atr = raw_move / episode.atr_m5

    return XauUnseenTransitionSnapshot(
        episode_id=episode.episode_id,
        birth_at=episode.birth_at,
        episode_side=episode.side,
        move_atr=episode.move_atr,
        latest_microbar_at=latest_microbar_at,
        geometry_5m=geometry_5m,
        geometry_15m=geometry_15m,
        transition_pattern=transition_pattern,
        transition_side=transition_side,
        transition_at=transition_at,
        transition_bars_waited=transition_bars_waited,
        transition_aligned=transition_aligned,
        move_consumed_atr=move_consumed_atr,
    )


def build_xau_unseen_transition_snapshot(
    episode: MarketOpportunityEpisode,
    bars: list[MarketBar],
    atr: list[float],
    microbars: list[XauMicrobarM1],
) -> XauUnseenTransitionSnapshot | None:
    return build_unseen_transition_snapshot(
        episode,
        bars,
        atr,
        microbars,
        symbol=SYMBOL,
    )


def capture_unseen_transition_snapshots(
    files_dir: Path,
    runtime_dir: Path,
    intelligence: TradingIntelligenceOverview,
    *,
    now: datetime,
    symbols: tuple[str, ...] = SUPPORTED_SYMBOLS,
) -> dict[str, int]:
    appended_by_symbol: dict[str, int] = {}
    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        if symbol not in SUPPORTED_SYMBOLS:
            continue

        microbars = load_xau_microbars(
            runtime_dir / microbar_ledger_file(symbol)
        )
        if len(microbars) < 5:
            appended_by_symbol[symbol] = 0
            continue

        bars = load_recent_closed_market_bars(
            files_dir,
            symbol,
            Timeframe.M5,
            now,
            limit=RECENT_M5_LIMIT,
        )
        if not bars:
            appended_by_symbol[symbol] = 0
            continue
        atr = _atr_series(bars)
        path = runtime_dir / unseen_transition_file(symbol)
        appended = 0
        for episode in intelligence.opportunities:
            snapshot = build_unseen_transition_snapshot(
                episode,
                bars,
                atr,
                microbars,
                symbol=symbol,
            )
            if snapshot is None:
                continue
            if append_unseen_transition_snapshot(path, snapshot):
                appended += 1
        appended_by_symbol[symbol] = appended

    return appended_by_symbol


def capture_xau_unseen_transition_snapshots(
    files_dir: Path,
    runtime_dir: Path,
    intelligence: TradingIntelligenceOverview,
    *,
    now: datetime,
) -> int:
    return capture_unseen_transition_snapshots(
        files_dir,
        runtime_dir,
        intelligence,
        now=now,
        symbols=(SYMBOL,),
    )[SYMBOL]
