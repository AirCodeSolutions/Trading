from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.blocked_probe import BlockedOpportunityProbe
from app.domain.demo_collection import DemoCollectionState
from app.domain.opportunity import OpportunityMechanism
from app.domain.shadow_paper import PaperTradeStatus, ShadowPaperTrade
from app.domain.trading import Side
from app.services.authority_regret import build_authority_regret_report

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 10, 1, 14, 0, tzinfo=TZ)
MECHANISM = OpportunityMechanism.STRUCTURAL_DISPLACEMENT_SEQUENCE


def trade(
    trade_id: str,
    *,
    signal_at: datetime,
    result_r: float,
) -> ShadowPaperTrade:
    return ShadowPaperTrade(
        trade_id=trade_id,
        symbol="XAUUSD",
        mechanism=MECHANISM,
        side=Side.BUY,
        signal_at=signal_at,
        entry_bar_at=signal_at,
        opened_at=signal_at,
        entry_price=100.1,
        stop_price=99.1,
        target_price=101.6,
        spread_at_entry=0.1,
        lots=1.0,
        risk_eur=100.0,
        risk_distance=1.0,
        target_r=1.5,
        max_holding_bars=12,
        status=(
            PaperTradeStatus.TARGET
            if result_r > 0
            else PaperTradeStatus.STOP
            if result_r < 0
            else PaperTradeStatus.TIMEOUT
        ),
        exit_at=signal_at + timedelta(minutes=5),
        exit_price=101.6 if result_r > 0 else 99.1,
        result_r=result_r,
        pnl_eur=result_r * 100.0,
        bars_held=1,
    )


def blocked(
    probe_id: str,
    *,
    signal_at: datetime,
    result_r: float,
    reason: str,
) -> BlockedOpportunityProbe:
    return BlockedOpportunityProbe(
        probe_id=probe_id,
        symbol="XAUUSD",
        mechanism=MECHANISM,
        side=Side.BUY,
        signal_at=signal_at,
        opened_at=signal_at,
        entry_price=100.1,
        stop_price=99.1,
        target_price=101.9,
        spread_at_entry=0.1,
        risk_distance=1.0,
        target_r=1.8,
        max_holding_bars=18,
        block_reason=reason,
        max_risk_approved=False,
        status=PaperTradeStatus.TARGET if result_r > 0 else PaperTradeStatus.STOP,
        exit_at=signal_at + timedelta(minutes=5),
        exit_price=101.9 if result_r > 0 else 99.1,
        result_r=result_r,
        bars_held=1,
    )


def write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(row.model_dump_json() + "\n" for row in rows),
        encoding="utf-8",
    )


def test_authority_regret_separates_accept_reject_and_guard(tmp_path: Path) -> None:
    t0 = NOW - timedelta(hours=2)
    accepted_broker = trade("paper-broker", signal_at=t0, result_r=1.5)
    accepted_paper = trade(
        "paper-only",
        signal_at=t0 + timedelta(minutes=5),
        result_r=-1.0,
    )
    rejected_win = trade(
        "rejected-win",
        signal_at=t0 + timedelta(minutes=10),
        result_r=1.5,
    )
    rejected_loss = trade(
        "rejected-loss",
        signal_at=t0 + timedelta(minutes=15),
        result_r=-1.0,
    )
    guard_win = blocked(
        "guard-win",
        signal_at=t0 + timedelta(minutes=20),
        result_r=1.8,
        reason="spread exceeds configured limit",
    )
    guard_loss = blocked(
        "guard-loss",
        signal_at=t0 + timedelta(minutes=25),
        result_r=-1.0,
        reason="minimum broker lot exceeds the risk budget",
    )

    write_jsonl(
        tmp_path / "XAUUSD_structural_displacement_sequence_paper_trades.jsonl",
        [accepted_broker, accepted_paper],
    )
    write_jsonl(
        tmp_path / "XAUUSD_structural_displacement_sequence_unqualified_probes.jsonl",
        [rejected_win, rejected_loss],
    )
    write_jsonl(
        tmp_path / "XAUUSD_structural_displacement_sequence_blocked_probes.jsonl",
        [guard_win, guard_loss],
    )
    (tmp_path / "demo_collection_state.json").write_text(
        DemoCollectionState(
            completed_trade_ids=["paper-broker"],
        ).model_dump_json(),
        encoding="utf-8",
    )

    report = build_authority_regret_report(
        tmp_path,
        now=NOW,
        window_hours=24,
    )

    assert report.accepted_resolved == 2
    assert report.accepted_winners == 1
    assert report.accepted_losers == 1
    assert report.accepted_total_r == 0.5
    assert report.broker_executed_resolved == 1
    assert report.broker_executed_winners == 1
    assert report.broker_executed_total_r == 1.5

    assert report.authority_rejected_resolved == 2
    assert report.winners_missed == 1
    assert report.winners_missed_r == 1.5
    assert report.losses_avoided == 1
    assert report.losses_avoided_r == 1.0
    assert report.rejected_counterfactual_total_r == 0.5

    assert report.guard_blocked_resolved == 2
    assert report.guard_blocked_winners == 1
    assert report.guard_blocked_losses == 1
    assert report.guard_blocked_total_r == 0.8


def test_guard_counterfactual_is_not_counted_as_authority_regret(
    tmp_path: Path,
) -> None:
    row = blocked(
        "guard-win",
        signal_at=NOW - timedelta(hours=1),
        result_r=1.8,
        reason="spread exceeds configured limit",
    )
    write_jsonl(tmp_path / "XAUUSD_x_blocked_probes.jsonl", [row])

    report = build_authority_regret_report(tmp_path, now=NOW, window_hours=24)

    assert report.authority_rejected_resolved == 0
    assert report.winners_missed == 0
    assert report.losses_avoided == 0
    assert report.guard_blocked_resolved == 1
    assert report.guard_blocked_total_r == 1.8


def test_window_and_broker_cost_limitations_are_explicit(tmp_path: Path) -> None:
    old = trade(
        "old",
        signal_at=NOW - timedelta(hours=25),
        result_r=1.5,
    )
    recent = trade(
        "recent",
        signal_at=NOW - timedelta(hours=1),
        result_r=1.5,
    )
    write_jsonl(
        tmp_path / "XAUUSD_x_unqualified_probes.jsonl",
        [old, recent],
    )

    report = build_authority_regret_report(tmp_path, now=NOW, window_hours=24)

    assert report.authority_rejected_resolved == 1
    assert report.rejected_counterfactual_total_r == 1.5
    assert report.recent[0].observation_id == "recent"
    assert report.recent[0].spread_cost_r == 0.1
    assert report.recent[0].broker_cost_adjusted_r is None
    assert report.recent[0].broker_cost_adjustment_complete is False
    assert all(
        bucket.broker_cost_adjusted_total_r is None
        for bucket in report.by_reason
    )
    assert "slippage" in report.cost_basis


def test_invalid_window_rejected(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="between 1 and 168"):
        build_authority_regret_report(tmp_path, now=NOW, window_hours=0)
