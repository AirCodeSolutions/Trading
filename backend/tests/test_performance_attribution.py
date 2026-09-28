from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.shadow_paper import PaperTradeStatus
from app.services.performance_attribution import build_performance_attribution_report

TZ = ZoneInfo("Europe/Athens")


def _trade(trade_id: str, mechanism: str, result: float, at: str) -> str:
    return f'{{"trade_id":"{trade_id}","symbol":"EURUSD","mechanism":"{mechanism}","side":"buy",' \
        f'"signal_at":"{at}","entry_bar_at":"{at}","opened_at":"{at}","entry_price":1.1,' \
        f'"stop_price":1.0,"target_price":1.2,"spread_at_entry":0.0001,"lots":1,' \
        f'"risk_eur":10,"risk_distance":0.1,"target_r":1,"max_holding_bars":12,' \
        f'"status":"{PaperTradeStatus.TARGET.value}","exit_at":"{at}","exit_price":1.2,"result_r":{result},"pnl_eur":{result * 10},"bars_held":3}}\n'


def test_attribution_keeps_admitted_probe_and_blocked_populations_separate(tmp_path: Path) -> None:
    at = "2026-09-28T10:00:00+03:00"
    (tmp_path / "EURUSD_directional_transition_paper_trades.jsonl").write_text(
        _trade("a", "directional_transition", 1.0, at), encoding="utf-8"
    )
    (tmp_path / "EURUSD_directional_transition_unqualified_probes.jsonl").write_text(
        _trade("p", "directional_transition", -1.0, at), encoding="utf-8"
    )
    report = build_performance_attribution_report(
        tmp_path, now=datetime(2026, 9, 28, 12, tzinfo=TZ), window_hours=24, symbols=("EURUSD",)
    )
    assert report.populations["admitted"] == 1
    assert report.populations["unqualified_probe"] == 1
    assert report.populations["blocked_probe"] == 0
    assert {row.population for row in report.summaries} == {"admitted", "unqualified_probe"}


def test_attribution_uses_broker_hour_and_chronological_drawdown(tmp_path: Path) -> None:
    path = tmp_path / "EURUSD_directional_transition_paper_trades.jsonl"
    path.write_text(
        _trade("a", "directional_transition", 1.0, "2026-09-28T10:00:00+03:00")
        + _trade("b", "directional_transition", -2.0, "2026-09-28T11:00:00+03:00"),
        encoding="utf-8",
    )
    report = build_performance_attribution_report(
        tmp_path, now=datetime(2026, 9, 28, 12, tzinfo=TZ), window_hours=24, symbols=("EURUSD",)
    )
    hour = next(row for row in report.summaries if row.dimension == "hour" and row.value == "11:00")
    assert hour.observations == 1
    mechanism = next(row for row in report.summaries if row.dimension == "mechanism")
    assert mechanism.max_drawdown_r == 2.0
    assert mechanism.expectancy_r == -0.5
