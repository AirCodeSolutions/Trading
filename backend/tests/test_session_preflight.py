import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.macro import MacroGateStatus
from app.domain.portfolio import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioRiskSnapshot,
    TradingOverview,
)
from app.domain.session import SessionRuntimeState, ShadowWorkerHeartbeat
from app.services.market_session import MarketSessionStatus, market_session_status
from app.services.session_preflight import (
    build_session_preflight,
    save_session_runtime_state,
)

TZ = ZoneInfo("Europe/Athens")
NOW = datetime(2026, 9, 18, 17, 30, tzinfo=TZ)


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


def mt4_wallclock_epoch(at: datetime) -> int:
    """MT4 epochs are parsed as server wall-clock values by the bridge."""
    return int(at.replace(tzinfo=UTC).timestamp())


def write_market(
    files_dir: Path,
    *,
    timestamp: int,
    include_spec: bool = True,
    m5_time: str = "17:20:00",
    symbol: str = "EURUSD",
    date: str = "20260918",
) -> None:
    (files_dir / f"{symbol}-M5.csv").write_text(
        f"{date},{m5_time},1.14,1.15,1.13,1.145,100\n",
        encoding="utf-8",
    )
    (files_dir / f"{symbol}-M15.csv").write_text(
        f"{date},17:15:00,1.14,1.15,1.13,1.145,300\n",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "timestamp": str(timestamp),
        "symbol": symbol,
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
    (files_dir / f"mt4_data_{symbol}.json").write_text(
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
    write_market(files_dir, timestamp=1789752548)
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
    write_market(files_dir, timestamp=1789689536)
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
    write_market(files_dir, timestamp=1789752548)
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
    write_market(files_dir, timestamp=1789752548, include_spec=False)
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
    write_market(files_dir, timestamp=1789752548)
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
        timestamp=1789752548,
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
        timestamp=1789752548,
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
        timestamp=1789752908,
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
        timestamp=1789752548,
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
        timestamp=1789753808,
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


def test_session_state_save_is_safe_under_concurrent_requests(tmp_path: Path) -> None:
    path = tmp_path / "session_state.json"

    def save(_: int) -> None:
        save_session_runtime_state(path, SessionRuntimeState())

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(save, range(100)))

    assert json.loads(path.read_text(encoding="utf-8")) == {"symbols": {}}


def test_market_session_profiles_are_timezone_aware_at_weekend_boundary() -> None:
    saturday = datetime(2026, 9, 26, 0, 1, tzinfo=TZ)
    assert market_session_status("BTCUSD", saturday) == MarketSessionStatus.OPEN
    for symbol in ("EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"):
        assert market_session_status(symbol, saturday) == MarketSessionStatus.CLOSED


def test_market_session_keeps_weekday_open_across_dst_aware_boundary() -> None:
    # Athens is UTC+3 before the October DST transition; Sunday/Monday is the
    # weekly boundary, so this Monday remains an open-session instant.
    monday = datetime(2026, 10, 26, 0, 1, tzinfo=TZ)
    assert market_session_status("EURUSD", monday) == MarketSessionStatus.OPEN


def test_market_session_converts_aware_input_to_mt4_server_timezone() -> None:
    # Sunday 22:01 UTC is already Monday 00:01 in Athens after DST ends.
    utc_sunday = datetime(2026, 10, 25, 22, 1, tzinfo=UTC)
    assert market_session_status("EURUSD", utc_sunday) == MarketSessionStatus.OPEN


def test_market_session_is_explicitly_unknown_for_unprofiled_symbol() -> None:
    assert market_session_status("UNKNOWN", NOW) == MarketSessionStatus.UNKNOWN


def test_preflight_marks_weekend_fx_and_metals_closed_without_degrading(
    tmp_path: Path,
) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    saturday = datetime(2026, 9, 26, 10, 0, tzinfo=TZ)
    symbols = ("BTCUSD", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD")
    for symbol in symbols:
        write_market(
            files_dir,
            timestamp=mt4_wallclock_epoch(saturday),
            symbol=symbol,
            date="20260926" if symbol == "BTCUSD" else "20260925",
            m5_time="09:55:00" if symbol == "BTCUSD" else "23:50:00",
        )
    write_heartbeat(runtime_dir, at=saturday)

    result = build_session_preflight(
        files_dir=files_dir,
        runtime_dir=runtime_dir,
        now=saturday,
        macro=macro(),
        overview=overview(),
        demo_execution_ready=False,
        watch_symbols=symbols,
    )

    assert result.status == "ready"
    assert result.ready_symbols == ["BTCUSD"]
    assert result.closed_symbols == ["EURUSD", "GBPUSD", "XAUUSD", "XAGUSD"]
    assert result.degraded_symbols == []
    assert [item.state for item in result.assets[1:]] == ["market_closed"] * 4


def test_preflight_degrades_stale_fx_during_open_weekday(tmp_path: Path) -> None:
    files_dir = tmp_path / "mt4"
    runtime_dir = tmp_path / "runtime"
    files_dir.mkdir()
    monday = datetime(2026, 9, 28, 10, 0, tzinfo=TZ)
    write_market(
        files_dir,
        timestamp=mt4_wallclock_epoch(monday),
        m5_time="09:00:00",
        date="20260928",
    )
    write_heartbeat(runtime_dir, at=monday)

    first = build_session_preflight(
        files_dir=files_dir, runtime_dir=runtime_dir, now=monday,
        macro=macro(), overview=overview(), demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )
    assert first.status == "warming_up"
    later = monday + timedelta(minutes=21)
    write_market(
        files_dir,
        timestamp=mt4_wallclock_epoch(later),
        m5_time="09:00:00",
        date="20260928",
    )
    write_heartbeat(runtime_dir, at=later)
    result = build_session_preflight(
        files_dir=files_dir, runtime_dir=runtime_dir, now=later,
        macro=macro(), overview=overview(), demo_execution_ready=False,
        watch_symbols=("EURUSD",),
    )
    assert result.status == "degraded"
    assert result.degraded_symbols == ["EURUSD"]
