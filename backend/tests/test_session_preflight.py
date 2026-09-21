import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.macro import MacroGateStatus
from app.domain.portfolio import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    TradingOverview,
)
from app.domain.session import ShadowWorkerHeartbeat
from app.services.session_preflight import build_session_preflight

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 19, 17, 30, tzinfo=TZ)


def overview() -> TradingOverview:
    return TradingOverview(
        at=NOW,
        broker=None,
        risk=PortfolioRiskSnapshot(
            reference_capital_eur=200,
            research_paper_closed_pnl_eur=0,
            research_paper_total_r=0,
            research_paper_open_risk_eur=0,
            research_paper_open_positions=0,
            selected_daily_pnl_eur=0,
            selected_daily_r=0,
            selected_open_risk_eur=0,
            selected_open_positions=0,
            max_daily_loss_eur=6,
            remaining_daily_loss_budget_eur=6,
        ),
        portfolio=PortfolioDecision(
            at=NOW,
            action=PortfolioAction.NO_TRADE,
            reason="test",
            historical_active=False,
            prospective_supports_demo=False,
        ),
        qualifications=[],
    )


def macro() -> MacroGateStatus:
    return MacroGateStatus(
        at=NOW,
        blocked=False,
        active_events=[],
        reason="clear",
    )


def write_market(
    files_dir: Path,
    *,
    timestamp: int,
    include_spec: bool = True,
    m5_time: str = "17:20:00",
) -> None:
    (files_dir / "EURUSD-M5.csv").write_text(
        f"20260919,{m5_time},1.14,1.15,1.13,1.145,100\n",
        encoding="utf-8",
    )
    (files_dir / "EURUSD-M15.csv").write_text(
        "20260919,17:15:00,1.14,1.15,1.13,1.145,300\n",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "timestamp": str(timestamp),
        "symbol": "EURUSD",
        "bid": "1.1450",
        "ask": "1.1451",
        "digits": "5",
    }
    if include_spec:
        payload["symbol_spec"] = {
            "tick_size": "0.00001",
            "tick_value": "0.87",
            "min_lot": "0.01",
            "max_lot": "100",
            "lot_step": "0.01",
            "margin_required": "100",
        }
    (files_dir / "mt4_data_EURUSD.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def write_heartbeat(
    runtime_dir: Path,
    *,
    at: datetime = NOW,
    ok: bool = True,
    warming_up_symbols: list[str] | None = None,
) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    heartbeat = ShadowWorkerHeartbeat(
        at=at,
        ok=ok,
        cost_samples_appended=1,
        shadow_scans=4,
        signals=0,
        paper_ready_symbols=["EURUSD"],
        warming_up_symbols=warming_up_symbols or [],
    )
    (runtime_dir / "worker_heartbeat.json").write_text(
        heartbeat.model_dump_json(),
        encoding="utf-8",
    )


def test_preflight_ready_when_non_btc_market_is_paper_ready(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(files_dir, timestamp=1789838948)
    write_heartbeat(runtime_dir)

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "ready"
    assert result.worker_ok is True
    assert result.ready_symbols == ["EURUSD"]


def test_preflight_waits_for_market_when_quote_is_stale(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(files_dir, timestamp=1789775936)
    write_heartbeat(runtime_dir)

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "waiting_market"
    assert result.waiting_symbols == ["EURUSD"]


def test_preflight_blocks_on_stale_worker_heartbeat(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(files_dir, timestamp=1789838948)
    write_heartbeat(runtime_dir, at=NOW - timedelta(minutes=4))

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "blocked"
    assert result.worker_ok is False
    assert result.worker_age_seconds == 240


def test_preflight_degrades_live_market_missing_spec(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(files_dir, timestamp=1789838948, include_spec=False)
    write_heartbeat(runtime_dir)

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "degraded"
    assert result.degraded_symbols == ["EURUSD"]


def test_preflight_reports_market_reopen_warmup(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(files_dir, timestamp=1789838948)
    write_heartbeat(runtime_dir, warming_up_symbols=["EURUSD"])

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "warming_up"
    assert result.warming_symbols == ["EURUSD"]
    assert result.ready_symbols == []


def test_preflight_waits_for_first_fresh_closed_m5_after_quote_returns(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    write_market(
        files_dir,
        timestamp=1789838948,
        m5_time="16:00:00",
    )
    write_heartbeat(runtime_dir)

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert result.status == "warming_up"
    assert result.warming_symbols == ["EURUSD"]
    assert "fresh closed M5" in result.assets[0].reason


def test_preflight_persists_quote_to_ready_timeline(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()

    write_market(
        files_dir,
        timestamp=1789838948,
        m5_time="16:00:00",
    )
    write_heartbeat(runtime_dir)

    first = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert first.status == "warming_up"
    assert first.timeline[0].quote_live_since == NOW
    assert first.timeline[0].first_fresh_m5_at is None

    fresh_now = NOW + timedelta(minutes=6)
    write_market(
        files_dir,
        timestamp=1789839308,
        m5_time="17:25:00",
    )
    write_heartbeat(runtime_dir, at=fresh_now)

    second = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=fresh_now,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert second.status == "ready"
    assert second.timeline[0].quote_live_since == NOW
    assert second.timeline[0].first_fresh_m5_at == fresh_now
    assert second.timeline[0].ready_at == fresh_now


def test_preflight_degrades_when_live_quote_outlives_stalled_m5(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()

    write_market(
        files_dir,
        timestamp=1789838948,
        m5_time="16:00:00",
    )
    write_heartbeat(runtime_dir)

    first = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=NOW,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )
    assert first.status == "warming_up"

    stalled_now = NOW + timedelta(minutes=21)
    write_market(
        files_dir,
        timestamp=1789840208,
        m5_time="16:00:00",
    )
    write_heartbeat(runtime_dir, at=stalled_now)

    stalled = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=stalled_now,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )

    assert stalled.status == "degraded"
    assert stalled.assets[0].state == "m5_stalled"
    assert stalled.degraded_symbols == ["EURUSD"]
    assert stalled.timeline[0].m5_stalled_at == stalled_now
