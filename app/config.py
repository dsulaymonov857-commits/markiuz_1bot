from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    encryption_key: str
    asl_base_url: str
    asl_api_key_header: str = "Authorization"
    asl_api_key_prefix: str = "Bearer"
    asl_api_key_check_path: str = "/public/api/v1/party/parties/tin/api-keys/check"
    asl_card_create_path: str
    asl_aggregation_create_path: str
    asl_timeout_seconds: float = Field(default=30, gt=0)
    database_path: str = "bot.db"
    moderation_host: str = "127.0.0.1"
    moderation_port: int = 8765

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
