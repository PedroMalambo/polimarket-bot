from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: str = Field(default="dev")
    APP_NAME: str = Field(default="polymarket-bot")
    LOG_LEVEL: str = Field(default="INFO")

    OPENAI_API_KEY: str | None = Field(default=None)
    OPENCLAW_GATEWAY_URL: str = Field(default="http://127.0.0.1:18789")

    POLYMARKET_API_BASE: str = Field(default="https://gamma-api.polymarket.com")
    POLYMARKET_CLOB_BASE: str = Field(default="https://clob.polymarket.com")
    POLYMARKET_WS_URL: str | None = Field(default=None)

    POLYGON_RPC_URL: str | None = Field(default=None)
    POLYGON_CHAIN_ID: int = Field(default=137)
    PRIVATE_KEY: str | None = Field(default=None)

    INITIAL_CAPITAL_USD: float = Field(default=20)
    KILL_SWITCH_USD: float = Field(default=10)
    TAKE_PROFIT_PRICE: float = Field(default=0.95)
    STOP_LOSS_PCT: float = Field(default=0.15)
    MAX_SLIPPAGE_PCT: float = Field(default=0.02)
    MAX_SPREAD: float = Field(default=0.02)
    MIN_MARKET_VOLUME_USD: float = Field(default=50000)
    MAX_OPEN_POSITIONS: int = Field(default=3)
    MARKET_COOLDOWN_MINUTES: int = Field(default=60)
    MAX_COMMITTED_CAPITAL_USD: float = Field(default=12)

    TELEGRAM_BOT_TOKEN: str | None = Field(default=None)
    TELEGRAM_CHAT_ID: str | None = Field(default=None)
    DISCORD_WEBHOOK_URL: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    return Settings()
