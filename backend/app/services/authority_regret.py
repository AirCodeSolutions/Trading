from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.authority_regret import (
    AuthorityDecision,
    AuthorityOutcome,
    AuthorityRegretBucket,
    AuthorityRegretObservation,
    AuthorityRegretReport,
)
from app.domain.shadow_paper import ShadowPaperTrade
from app.services.blocked_probe import load_closed_probes
from app.services.demo_collection import load_demo_collection_state
from app.services.shadow_paper import load_closed_trades


def _strategy_id(symbol: str, mechanism) -> str:
    return f"{symbol}:{mechanism.value}"


def _outcome(result_r: float) -> AuthorityOutcome:
    if result_r > 0:
        return AuthorityOutcome.WIN
    if result_r < 0:
        return AuthorityOutcome.LOSS
    return AuthorityOutcome.FLAT


def _spread_cost_r(spread: float, risk_distance: float) -> float | None:
    if risk_distance <= 0:
        return None
    return spread / risk_distance


def _paper_observation(
    trade: ShadowPaperTrade,
    *,
    broker_executed: bool,
) -> AuthorityRegretObservation:
    if trade.result_r is None:
        raise ValueError("authority-regret paper observation requires resolved result")
    return AuthorityRegretObservation(
        observation_id=trade.trade_id,
        strategy_id=_strategy_id(trade.symbol, trade.mechanism),
        symbol=trade.symbol,
        mechanism=trade.mechanism,
        signal_at=trade.signal_at,
        decision=(
            AuthorityDecision.BROKER_DEMO_EXECUTED
            if broker_executed
            else AuthorityDecision.PAPER_ACCEPTED
        ),
        reason=(
            "broker_demo_authorized"
            if broker_executed
            else "paper_admission_allowed"
        ),
        outcome=_outcome(float(trade.result_r)),
        result_r=float(trade.result_r),
        spread_cost_r=_spread_cost_r(
            trade.spread_at_entry,
            trade.risk_distance,
        ),
    )


def _unqualified_observation(
    trade: ShadowPaperTrade,
) -> AuthorityRegretObservation:
    if trade.result_r is None:
        raise ValueError("authority-regret probe requires resolved result")
    return AuthorityRegretObservation(
        observation_id=trade.trade_id,
        strategy_id=_strategy_id(trade.symbol, trade.mechanism),
        symbol=trade.symbol,
        mechanism=trade.mechanism,
        signal_at=trade.signal_at,
        decision=AuthorityDecision.AUTHORITY_REJECTED,
        reason="paper_authority_not_granted",
        outcome=_outcome(float(trade.result_r)),
        result_r=float(trade.result_r),
        spread_cost_r=_spread_cost_r(
            trade.spread_at_entry,
            trade.risk_distance,
        ),
    )
def _blocked_observation(probe) -> AuthorityRegretObservation:
    if probe.result_r is None:
        raise ValueError("authority-regret blocked probe requires resolved result")
    return AuthorityRegretObservation(
        observation_id=probe.probe_id,
        strategy_id=_strategy_id(probe.symbol, probe.mechanism),
        symbol=probe.symbol,
        mechanism=probe.mechanism,
        signal_at=probe.signal_at,
        decision=AuthorityDecision.ECONOMIC_GUARD_BLOCKED,
        reason=probe.block_reason or "economic_guard_blocked",
        outcome=_outcome(float(probe.result_r)),
        result_r=float(probe.result_r),
        spread_cost_r=_spread_cost_r(
            probe.spread_at_entry,
            probe.risk_distance,
        ),
    )


def _bucket(
    key: str,
    rows: list[AuthorityRegretObservation],
) -> AuthorityRegretBucket:
    values = [row.result_r for row in rows]
    adjusted = [
        row.broker_cost_adjusted_r
        for row in rows
        if row.broker_cost_adjusted_r is not None
    ]
    adjustment_complete = bool(rows) and len(adjusted) == len(rows)
    return AuthorityRegretBucket(
        key=key,
        observations=len(rows),
        wins=sum(row.outcome == AuthorityOutcome.WIN for row in rows),
        losses=sum(row.outcome == AuthorityOutcome.LOSS for row in rows),
        flats=sum(row.outcome == AuthorityOutcome.FLAT for row in rows),
        total_r=sum(values),
        expectancy_r=(sum(values) / len(values) if values else None),
        positive_r=sum(value for value in values if value > 0),
        negative_r=sum(value for value in values if value < 0),
        broker_cost_adjusted_total_r=(
            sum(adjusted) if adjustment_complete else None
        ),
        broker_cost_adjustment_complete=adjustment_complete,
    )


def _group_buckets(
    rows: list[AuthorityRegretObservation],
    *,
    key_fn,
) -> list[AuthorityRegretBucket]:
    grouped: dict[str, list[AuthorityRegretObservation]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return [
        _bucket(key, grouped[key])
        for key in sorted(grouped)
    ]


def _resolved_paper_rows(
    runtime_dir: Path,
) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_paper_trades.jsonl")):
        rows.extend(load_closed_trades(path))
    return rows


def _resolved_unqualified_rows(
    runtime_dir: Path,
) -> list[ShadowPaperTrade]:
    rows: list[ShadowPaperTrade] = []
    for path in sorted(runtime_dir.glob("*_unqualified_probes.jsonl")):
        rows.extend(load_closed_trades(path))
    return rows
def build_authority_regret_report(
    runtime_dir: Path,
    *,
    now: datetime,
    window_hours: int = 168,
) -> AuthorityRegretReport:
    if window_hours < 1 or window_hours > 168:
        raise ValueError("window_hours must be between 1 and 168")

    window_start = now - timedelta(hours=window_hours)
    demo_state = load_demo_collection_state(
        runtime_dir / "demo_collection_state.json"
    )
    completed_demo_trade_ids = set(demo_state.completed_trade_ids)

    observations: list[AuthorityRegretObservation] = []

    for trade in _resolved_paper_rows(runtime_dir):
        if trade.result_r is None or not (window_start <= trade.signal_at <= now):
            continue
        observations.append(
            _paper_observation(
                trade,
                broker_executed=trade.trade_id in completed_demo_trade_ids,
            )
        )

    for trade in _resolved_unqualified_rows(runtime_dir):
        if trade.result_r is None or not (window_start <= trade.signal_at <= now):
            continue
        observations.append(_unqualified_observation(trade))

    for path in sorted(runtime_dir.glob("*_blocked_probes.jsonl")):
        for probe in load_closed_probes(path):
            if probe.result_r is None or not (
                window_start <= probe.signal_at <= now
            ):
                continue
            observations.append(_blocked_observation(probe))

    observations.sort(key=lambda row: (row.signal_at, row.observation_id))

    accepted = [
        row
        for row in observations
        if row.decision
        in {
            AuthorityDecision.PAPER_ACCEPTED,
            AuthorityDecision.BROKER_DEMO_EXECUTED,
        }
    ]
    broker_executed = [
        row
        for row in observations
        if row.decision == AuthorityDecision.BROKER_DEMO_EXECUTED
    ]
    rejected = [
        row
        for row in observations
        if row.decision == AuthorityDecision.AUTHORITY_REJECTED
    ]
    guard_blocked = [
        row
        for row in observations
        if row.decision == AuthorityDecision.ECONOMIC_GUARD_BLOCKED
    ]

    return AuthorityRegretReport(
        generated_at=now,
        window_hours=window_hours,
        window_start=window_start,
        window_end=now,
        accepted_resolved=len(accepted),
        accepted_winners=sum(
            row.outcome == AuthorityOutcome.WIN for row in accepted
        ),
        accepted_losers=sum(
            row.outcome == AuthorityOutcome.LOSS for row in accepted
        ),
        accepted_total_r=sum(row.result_r for row in accepted),
        broker_executed_resolved=len(broker_executed),
        broker_executed_winners=sum(
            row.outcome == AuthorityOutcome.WIN for row in broker_executed
        ),
        broker_executed_losers=sum(
            row.outcome == AuthorityOutcome.LOSS for row in broker_executed
        ),
        broker_executed_total_r=sum(
            row.result_r for row in broker_executed
        ),
        authority_rejected_resolved=len(rejected),
        winners_missed=sum(
            row.outcome == AuthorityOutcome.WIN for row in rejected
        ),
        winners_missed_r=sum(
            row.result_r for row in rejected if row.result_r > 0
        ),
        losses_avoided=sum(
            row.outcome == AuthorityOutcome.LOSS for row in rejected
        ),
        losses_avoided_r=-sum(
            row.result_r for row in rejected if row.result_r < 0
        ),
        rejected_counterfactual_total_r=sum(
            row.result_r for row in rejected
        ),
        guard_blocked_resolved=len(guard_blocked),
        guard_blocked_winners=sum(
            row.outcome == AuthorityOutcome.WIN for row in guard_blocked
        ),
        guard_blocked_losses=sum(
            row.outcome == AuthorityOutcome.LOSS for row in guard_blocked
        ),
        guard_blocked_total_r=sum(
            row.result_r for row in guard_blocked
        ),
        by_reason=_group_buckets(
            observations,
            key_fn=lambda row: f"{row.decision.value}:{row.reason}",
        ),
        by_strategy=_group_buckets(
            observations,
            key_fn=lambda row: f"{row.strategy_id}:{row.decision.value}",
        ),
        recent=observations[-50:][::-1],
        cost_basis=(
            "result_r is spread-aware from the persisted PAPER/probe geometry; "
            "broker slippage and commissions are not inferred for counterfactual "
            "observations, so broker_cost_adjusted_r remains unavailable unless "
            "an exact broker fill can be paired"
        ),
        limitations=[
            "Unqualified probes measure executable opportunities rejected from PAPER authority.",
            "Economic-guard blocked probes are reported separately and are never counted as executable authority regret.",
            "PAPER accepted outcomes are not equivalent to broker execution.",
            "Broker-executed tagging uses exact completed PAPER trade ids from demo_collection_state.",
            "No current admission state is backfilled as a historical rejection reason.",
        ],
    )
