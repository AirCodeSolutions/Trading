from enum import StrEnum

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

    model_config = SettingsConfigDict(
        env_prefix="TRADING_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
