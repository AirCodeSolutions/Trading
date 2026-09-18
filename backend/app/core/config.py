from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutionMode(StrEnum):
    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class Settings(BaseSettings):
    app_name: str = "Trading"
    api_prefix: str = "/api/v1"
    execution_mode: ExecutionMode = ExecutionMode.PAPER
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

    model_config = SettingsConfigDict(
        env_prefix="TRADING_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
