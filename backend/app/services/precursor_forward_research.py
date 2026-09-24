from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from app.domain.causal_precursor import CausalPrecursorObservation
from app.domain.market import MarketBar, Timeframe
from app.domain.precursor_forward_research import (
    PrecursorForwardOutcome,
    PrecursorForwardResearchReport,
    PrecursorForwardSummary,
)
from app.domain.trading import Side
from app.domain.trading_intelligence import OpportunityCausalPattern
from app.services.causal_precursor import (
    load_causal_precursor_collection_state,
    load_causal_precursors,
)
from app.services.mt4_market_data import load_recent_closed_market_bars
from app.services.trading_intelligence import _atr_series

DEFAULT_HORIZON_BARS = 12


def build_precursor_forward_research(
    files_dir: Path,
    runtime_dir: Path,
    *,
    now: datetime,
    symbols: Iterable[str],
    horizon_bars: int = DEFAULT_HORIZON_BARS,
) -> PrecursorForwardResearchReport:
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be positive")
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    state = load_causal_precursor_collection_state(runtime_dir)
    if state is None:
        return _empty_report(now, horizon_bars)

    allowed = tuple(symbol.upper() for symbol in symbols)
    lookback_start = state.started_at - timedelta(minutes=5)
    observations = load_causal_precursors(
        runtime_dir,
        window_start=lookback_start,
        window_end=now,
        symbols=allowed,
    )
    grouped: dict[str, list[CausalPrecursorObservation]] = defaultdict(list)
    for row in observations:
        grouped[row.symbol.upper()].append(row)

    outcomes: list[PrecursorForwardOutcome] = []
    pending = 0
    for symbol in allowed:
        rows = grouped.get(symbol, [])
        if not rows:
            continue
        # Load enough recent M5 bars to cover the prospective collection window
        # and the complete forward horizon without reading unrelated history.
        elapsed_minutes = max(
            0.0,
            (now - state.started_at).total_seconds() / 60.0,
        )
        limit = max(
            100,
            int(elapsed_minutes / 5) + horizon_bars + 64,
        )
        bars = load_recent_closed_market_bars(
            files_dir,
            symbol,
            Timeframe.M5,
            now,
            limit=limit,
        )
        resolved, unresolved = _resolve_symbol_outcomes(
            rows,
            bars,
            horizon_bars=horizon_bars,
        )
        outcomes.extend(resolved)
        pending += unresolved

    independent = _independent_outcomes(outcomes, horizon_bars=horizon_bars)
    by_pattern = [
        _summary(
            label=pattern.value,
            raw=[row for row in outcomes if row.pattern == pattern],
            independent=[
                row for row in independent if row.pattern == pattern
            ],
        )
        for pattern in OpportunityCausalPattern
        if any(row.pattern == pattern for row in outcomes)
    ]
    by_symbol = [
        _summary(
            label=symbol,
            raw=[row for row in outcomes if row.symbol == symbol],
            independent=[row for row in independent if row.symbol == symbol],
        )
        for symbol in sorted({row.symbol for row in outcomes})
    ]

    return PrecursorForwardResearchReport(
        generated_at=now,
        prospective_started_at=state.started_at,
        horizon_bars=horizon_bars,
        raw_resolved=len(outcomes),
        independent_resolved=len(independent),
        pending=pending,
        overall=_summary(
            label="all",
            raw=outcomes,
            independent=independent,
        ),
        by_pattern=by_pattern,
        by_symbol=by_symbol,
        recent_independent=sorted(
            independent,
            key=lambda row: row.first_seen_at,
            reverse=True,
        )[:50],
    )


def _resolve_symbol_outcomes(
    observations: Sequence[CausalPrecursorObservation],
    bars: Sequence[MarketBar],
    *,
    horizon_bars: int,
) -> tuple[list[PrecursorForwardOutcome], int]:
    if not bars:
        return [], len(observations)

    index_by_timestamp = {
        bar.timestamp: index for index, bar in enumerate(bars)
    }
    atr = _atr_series(list(bars))
    outcomes: list[PrecursorForwardOutcome] = []
    pending = 0

    for observation in observations:
        index = index_by_timestamp.get(observation.latest_closed_m5_at)
        if index is None or index >= len(atr):
            continue
        end = index + horizon_bars
        if end >= len(bars):
            pending += 1
            continue
        current_atr = atr[index]
        if current_atr <= 0:
            continue

        reference = bars[index].close
        future = bars[index + 1 : end + 1]
        if observation.side == Side.BUY:
            favorable = max(bar.high for bar in future) - reference
            adverse = reference - min(bar.low for bar in future)
            close_return = future[-1].close - reference
        else:
            favorable = reference - min(bar.low for bar in future)
            adverse = max(bar.high for bar in future) - reference
            close_return = reference - future[-1].close

        favorable_atr = max(0.0, favorable / current_atr)
        adverse_atr = max(0.0, adverse / current_atr)
        signed_close_atr = close_return / current_atr
        outcomes.append(
            PrecursorForwardOutcome(
                symbol=observation.symbol.upper(),
                pattern=observation.pattern,
                side=observation.side,
                first_seen_at=observation.first_seen_at,
                horizon_end_at=future[-1].timestamp + timedelta(minutes=5),
                atr_m5=current_atr,
                favorable_mfe_atr=favorable_atr,
                adverse_mae_atr=adverse_atr,
                signed_close_return_atr=signed_close_atr,
                favorable_dominates=favorable_atr > adverse_atr,
                close_aligned=signed_close_atr > 0,
            )
        )

    return outcomes, pending


def _independent_outcomes(
    outcomes: Sequence[PrecursorForwardOutcome],
    *,
    horizon_bars: int,
) -> list[PrecursorForwardOutcome]:
    selected: list[PrecursorForwardOutcome] = []
    next_allowed: dict[str, datetime] = {}
    horizon = timedelta(minutes=5 * horizon_bars)

    for row in sorted(outcomes, key=lambda item: item.first_seen_at):
        allowed_at = next_allowed.get(row.symbol)
        if allowed_at is not None and row.first_seen_at < allowed_at:
            continue
        selected.append(row)
        next_allowed[row.symbol] = row.first_seen_at + horizon
    return selected


def _summary(
    *,
    label: str,
    raw: Sequence[PrecursorForwardOutcome],
    independent: Sequence[PrecursorForwardOutcome],
) -> PrecursorForwardSummary:
    rows = list(independent)
    if not rows:
        return PrecursorForwardSummary(
            label=label,
            raw_resolved=len(raw),
            independent_resolved=0,
            average_favorable_mfe_atr=0.0,
            average_adverse_mae_atr=0.0,
            average_signed_close_return_atr=0.0,
            favorable_dominance_rate=0.0,
            close_alignment_rate=0.0,
        )

    return PrecursorForwardSummary(
        label=label,
        raw_resolved=len(raw),
        independent_resolved=len(rows),
        average_favorable_mfe_atr=fmean(
            row.favorable_mfe_atr for row in rows
        ),
        average_adverse_mae_atr=fmean(
            row.adverse_mae_atr for row in rows
        ),
        average_signed_close_return_atr=fmean(
            row.signed_close_return_atr for row in rows
        ),
        favorable_dominance_rate=(
            sum(row.favorable_dominates for row in rows) / len(rows)
        ),
        close_alignment_rate=(
            sum(row.close_aligned for row in rows) / len(rows)
        ),
    )


def _empty_report(
    now: datetime,
    horizon_bars: int,
) -> PrecursorForwardResearchReport:
    return PrecursorForwardResearchReport(
        generated_at=now,
        prospective_started_at=None,
        horizon_bars=horizon_bars,
        raw_resolved=0,
        independent_resolved=0,
        pending=0,
        overall=PrecursorForwardSummary(
            label="all",
            raw_resolved=0,
            independent_resolved=0,
            average_favorable_mfe_atr=0.0,
            average_adverse_mae_atr=0.0,
            average_signed_close_return_atr=0.0,
            favorable_dominance_rate=0.0,
            close_alignment_rate=0.0,
        ),
    )
