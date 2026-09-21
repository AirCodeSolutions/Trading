from pathlib import Path

from app.core.config import settings

ACTIVE_MARKETS = (
    "BTCUSD",
    "EURUSD",
    "GBPUSD",
    "XAUUSD",
    "XAGUSD",
)


def test_backend_watchlist_is_restricted_to_active_markets() -> None:
    assert settings.session_watch_symbols == ACTIVE_MARKETS


def test_mt4_exporter_default_symbols_match_active_markets() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "mt4" / "TradingMarketExporter.mq4").read_text(
        encoding="utf-8"
    )

    assert (
        'input string SymbolsCsv = "BTCUSD,EURUSD,GBPUSD,XAUUSD,XAGUSD";'
        in source
    )
    for abandoned in (
        "US500Cash",
        "USA500IDXUSD",
        "USATECHIDXUSD",
        "Volatility",
        "VOLIDXUSD",
    ):
        assert abandoned not in source


def test_runtime_children_do_not_inherit_startup_lock() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "ops" / "start_trading.sh").read_text(encoding="utf-8")

    assert source.count("exec 9>&-") >= 3
