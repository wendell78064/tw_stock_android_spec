from functools import lru_cache
from secrets import token_urlsafe

from pydantic import Field, SecretStr, field_validator, model_validator
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
    realtime_provider: str = "unconfigured"
    shioaji_api_key: SecretStr | None = None
    shioaji_secret_key: SecretStr | None = None
    shioaji_simulation: bool = False
    p1_alert_realtime_enabled: bool = False
    realtime_broker_subscription_budget: int | None = Field(default=None, gt=0)

    @field_validator("realtime_broker_subscription_budget", mode="before")
    @classmethod
    def empty_budget_is_unconfigured(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_realtime_capacity(self):
        if (
            self.p1_alert_realtime_enabled
            and self.realtime_broker_subscription_budget is None
        ):
            raise ValueError("P1 realtime requires an explicit broker subscription budget")
        return self

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
