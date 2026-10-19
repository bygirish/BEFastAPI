"""Settings bases (rule X-4).

`PlatformSettings` holds process-wide infrastructure settings. Each service defines its
own `ServiceSettings` subclass with a unique env prefix (``AUTH_``, ``FILES_`` …) and
never reads another service's settings.
"""

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATFORM_", extra="ignore", populate_by_name=True)

    env: Environment = Field(default="local", validation_alias=AliasChoices("ENV", "PLATFORM_ENV"))
    app_version: str = Field(
        default="dev", validation_alias=AliasChoices("APP_VERSION", "PLATFORM_APP_VERSION")
    )
    log_level: str = "INFO"
    redis_url: str | None = None

    @property
    def is_production(self) -> bool:
        return self.env == "production"


class ServiceSettings(BaseSettings):
    """Base for per-service settings. Subclasses set ``env_prefix`` in ``model_config``."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "sqlite+aiosqlite:///:memory:"
    db_pool_size: int = 5
    db_max_overflow: int = 5
