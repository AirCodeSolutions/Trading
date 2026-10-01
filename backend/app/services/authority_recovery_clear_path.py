from datetime import datetime, timedelta
from pathlib import Path

from app.domain.authority_recovery_clear_path import (
    ClearPathEvidenceState,
    ClearPathRecoveryReport,
    ClearPathWindowMetrics,
)
from app.domain.shadow_paper import ShadowPaperTrade
from app.domain.trading import Side
from app.services.shadow_paper import load_closed_trades

HYPOTHESIS_ID = "recover_rejected_clear_path_to_existing_target_v1"
MIN_SELECTED_OBSERVATIONS = 20
MIN_PROFIT_FACTOR = 1.05
MAX_DRAWDOWN_R = 12.0

_LANDMARK_NAMES = (
    "previous_day_high",
    "previous_day_low",
    "asia_high",
    "asia_low",
    "london_high_so_far",
    "london_low_so_far",
    "us_high_so_far",
    "us_low_so_far",
)


def _resolved_unqualified_rows(runtime_dir: Path) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        rows.extend(load_closed_trades(path))
    return rows


def clear_path_to_existing_target(trade: ShadowPaperTrade) -> tuple[bool, str | None]:
    context = trade.session_landmark_context
    if context is None:
        return False, None
    levels = [
        (name, getattr(context, name))
        for name in _LANDMARK_NAMES
        if getattr(context, name) is not None
    ]
    if trade.side is Side.BUY:
        favorable = [(name, price) for name, price in levels if price > trade.entry_price]
    else:
        favorable = [(name, price) for name, price in levels if price < trade.entry_price]
    if not favorable:
        return False, None
    name, price = min(favorable, key=lambda item: abs(item[1] - trade.entry_price))
    if trade.side is Side.BUY:
        return price >= trade.target_price, name
    return price <= trade.target_price, name


def _metrics(rows: list[ShadowPaperTrade]) -> ClearPathWindowMetrics:
    values = [float(row.result_r) for row in rows if row.result_r is not None]
    gains = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return ClearPathWindowMetrics(
        observations=len(values),
        wins=sum(v > 0 for v in values),
        losses=sum(v < 0 for v in values),
        flats=sum(v == 0 for v in values),
        total_r=sum(values),
        expectancy_r=(sum(values) / len(values) if values else None),
        profit_factor=(gains / losses if losses > 0 else (99.0 if gains > 0 else 0.0)),
        max_drawdown_r=drawdown,
    )


def build_clear_path_recovery_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
) -> ClearPathRecoveryReport:
    if window_hours < 1 or window_hours > 168:
        raise ValueError("window_hours must be between 1 and 168")
    start = now - timedelta(hours=window_hours)
    split = start + timedelta(hours=window_hours / 2)
    rows = [
        row
        for row in _resolved_unqualified_rows(runtime_dir)
        if row.result_r is not None and start <= row.signal_at <= now
    ]
    rows.sort(key=lambda row: (row.signal_at, row.trade_id))
    with_context = [row for row in rows if row.session_landmark_context is not None]
    selected = [row for row in with_context if clear_path_to_existing_target(row)[0]]
    metrics = _metrics(selected)
    older = _metrics([row for row in selected if row.signal_at < split])
    recent = _metrics([row for row in selected if row.signal_at >= split])
    enough = metrics.observations >= MIN_SELECTED_OBSERVATIONS
    economically_ok = (
        (metrics.expectancy_r or 0.0) > 0
        and metrics.profit_factor >= MIN_PROFIT_FACTOR
        and metrics.max_drawdown_r <= MAX_DRAWDOWN_R
    )
    state = (
        ClearPathEvidenceState.INSUFFICIENT_EVIDENCE
        if not enough
        else ClearPathEvidenceState.REVIEW_READY
        if economically_ok
        else ClearPathEvidenceState.ECONOMICALLY_REJECTED
    )
    return ClearPathRecoveryReport(
        generated_at=now,
        window_hours=window_hours,
        hypothesis_id=HYPOTHESIS_ID,
        resolved_unqualified=len(rows),
        context_available=len(with_context),
        selected_resolved=metrics.observations,
        selection_rate=(metrics.observations / len(with_context) if with_context else 0.0),
        selected=metrics,
        older_half=older,
        recent_half=recent,
        minimum_observations=MIN_SELECTED_OBSERVATIONS,
        required_additional_observations=max(0, MIN_SELECTED_OBSERVATIONS - metrics.observations),
        evidence_state=state,
        supports_demo=False,
        authority_effect=False,
        human_review_required=True,
        limitations=[
            "Only resolved executable unqualified probes are evaluated.",
            "Landmarks are persisted causal context captured at signal time; no future level is reconstructed.",
            "No new numeric selector threshold is introduced: the nearest favorable known landmark must simply not sit before the existing target.",
            "Existing prospective criteria are reused: N>=20, positive expectancy, PF>=1.05 and DD<=12R.",
            "REVIEW_READY never grants SUPPORTS_DEMO automatically and still requires human review.",
        ],
    )
