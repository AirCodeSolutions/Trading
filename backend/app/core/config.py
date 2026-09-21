from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.approval import DecisionMode


class ExecutionMode(StrEnum):
    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class Settings(BaseSettings):
    app_name: str = "Trading"
    api_prefix: str = "/api/v1"
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    decision_mode: DecisionMode = DecisionMode.CONFIRM
    live_trading_enabled: bool = False
    allowed_timeframes: tuple[str, ...] = ("M5", "M15")

    reference_capital_eur: float = 200.0
    risk_per_trade_fraction: float = 0.01
    absolute_max_risk_fraction: float = 0.02
    max_daily_loss_fraction: float = 0.03
    max_spread_to_stop: float = 0.15
    max_margin_fraction: float = 0.25

    mt4_files_dir: Path | None = None
    mt4_server_timezone: str = "Europe/Athens"
    shadow_ledger_dir: Path = Path("runtime/shadow")
    shadow_collection_interval_seconds: int = 30
    session_watch_symbols: tuple[str, ...] = (
        "BTCUSD",
        "EURUSD",
        "GBPUSD",
        "XAUUSD",
        "XAGUSD",
    )

    macro_events_path: Path = Path("config/macro_events_2026.json")
    research_execution_profile_path: Path = Path(
        "config/research_execution_profile_2026-09-21.json"
    )
    paper_evidence_cutover_at: datetime = datetime.fromisoformat(
        "2026-09-20T12:53:56+03:00"
    )

    demo_execution_bridge_enabled: bool = False
    demo_magic_number: int = 560619
    demo_max_slippage_points: int = 100

    model_config = SettingsConfigDict(
        env_prefix="TRADING_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
