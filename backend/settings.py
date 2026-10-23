"""Typed application settings (environment + .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Signal — Social Sentiment Intelligence"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
    api_key: str = ""  # empty = uploads open (local/demo); set for any public deployment
    max_upload_mb: int = 50
    cache_ttl_seconds: int = 120
    research_cache_ttl_seconds: int = 600
    rate_limit_per_minute: int = 120
    negative_sentiment_alert_threshold: float = 40.0
    enable_docs: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
