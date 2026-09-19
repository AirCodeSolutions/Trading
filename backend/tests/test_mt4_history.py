from pathlib import Path

from app.domain.market import Timeframe
from app.services.mt4_history import resolve_mt4_history_path


def test_prefers_closed_bar_research_export(tmp_path: Path) -> None:
    research = tmp_path / "mt4_research_bars_XAUUSD_M5.csv"
    fallback = tmp_path / "XAUUSD-M5.csv"
    research.write_text("research", encoding="utf-8")
    fallback.write_text("fallback", encoding="utf-8")

    result = resolve_mt4_history_path(tmp_path, "xauusd", Timeframe.M5)

    assert result == research


def test_uses_legacy_history_when_research_export_is_missing(tmp_path: Path) -> None:
    fallback = tmp_path / "EURUSD-M15.csv"
    fallback.write_text("fallback", encoding="utf-8")

    result = resolve_mt4_history_path(tmp_path, "eurusd", Timeframe.M15)

    assert result == fallback
