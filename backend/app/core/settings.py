from functools import lru_cache
from secrets import token_urlsafe

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TW Market Ledger API"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://twstock:twstock@localhost:5432/twstock"
    redis_url: str = "redis://localhost:6379/0"
    admin_api_key: str = "admin-secret-key"
    auth_mode: str = "LOCAL"
    auth_secret: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    sync_page_limit: int = 100

    def effective_auth_secret(self) -> str:
        if self.auth_secret:
            return self.auth_secret
        if self.app_env.lower() in {"production", "prod"}:
            raise ValueError("AUTH_SECRET is required in production")
        if not hasattr(self, "_development_auth_secret"):
            object.__setattr__(self, "_development_auth_secret", token_urlsafe(48))
        return self._development_auth_secret

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
