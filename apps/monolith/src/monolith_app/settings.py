from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class MonolithSettings(BaseSettings):
    """Process-level wiring settings. Service-specific settings stay in each service (rule X-4)."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    # Comma-separated service names; empty = every installed service.
    enabled_services: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validation_alias="ENABLED_SERVICES"
    )
    service_name: str = Field(default="befastapi-monolith", validation_alias="OTEL_SERVICE_NAME")

    # Token verification (Auth issues tokens; everyone verifies locally via JWKS — rule X-1)
    jwt_issuer: str | None = Field(default=None, validation_alias="JWT_ISSUER")
    jwt_audience: str | None = Field(default=None, validation_alias="JWT_AUDIENCE")
    jwt_jwks_url: str | None = Field(default=None, validation_alias="JWT_JWKS_URL")

    @field_validator("enabled_services", mode="before")
    @classmethod
    def _split(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
