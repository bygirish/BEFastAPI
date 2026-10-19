from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import NoDecode, SettingsConfigDict

from notifications_service.domain.providers import DEV_ONLY_PROVIDERS, PROVIDER_NAMES
from platform_core.settings import Environment, ServiceSettings

_DEV_PEPPER = "dev-only-pepper-change-me"


class NotificationsSettings(ServiceSettings):
    """NOTIFICATIONS_* environment variables. Never read by other services (rule X-4).

    Provider chains are comma-separated, tried left to right: NOTIFICATIONS_EMAIL_PROVIDERS=smtp,console.
    """

    model_config = SettingsConfigDict(env_prefix="NOTIFICATIONS_", extra="ignore")

    # The process environment (shared ENV variable), needed for the production guard below.
    env: Environment = Field(default="local", validation_alias=AliasChoices("ENV", "PLATFORM_ENV"))

    sms_providers: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["console"])
    email_providers: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["console"])
    attempt_timeout_seconds: float = Field(default=5.0, gt=0)

    # Abuse protection: at most this many deliveries per recipient per hour (SMS pumping costs real money).
    rate_limit_per_hour: int = Field(default=5, ge=1)
    digest_pepper: SecretStr = SecretStr(_DEV_PEPPER)

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@befastapi.local"

    # What the 'static' provider answers: accept | reject | unavailable (deterministic tests and demos).
    static_outcome: Literal["accept", "reject", "unavailable"] = "accept"

    # Mount POST /api/v1/notifications/dev/send (+ a viewer of the in-memory sender). Never in production.
    dev_endpoints: bool = False

    @field_validator("sms_providers", "email_providers", mode="before")
    @classmethod
    def _split(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("sms_providers", "email_providers")
    @classmethod
    def _known_providers(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - PROVIDER_NAMES)
        if unknown:
            raise ValueError(f"unknown provider(s) {unknown}; choose from {sorted(PROVIDER_NAMES)}")
        return value

    @model_validator(mode="after")
    def _production_guard(self) -> "NotificationsSettings":
        """Rule X-11: dev-only senders and endpoints refuse to start in production.

        A console sender in production would print one-time codes into the logs; a static sender would claim
        success without sending anything. Failing at start-up beats failing silently at 3 a.m.
        """
        if self.env != "production":
            return self
        problems: list[str] = []
        used_dev = DEV_ONLY_PROVIDERS & {*self.sms_providers, *self.email_providers}
        if used_dev:
            problems.append(f"dev-only providers {sorted(used_dev)} are configured")
        if self.dev_endpoints:
            problems.append("NOTIFICATIONS_DEV_ENDPOINTS is enabled")
        if self.digest_pepper.get_secret_value() == _DEV_PEPPER:
            problems.append("NOTIFICATIONS_DIGEST_PEPPER is still the development default")
        if problems:
            raise ValueError("refusing to start in production: " + "; ".join(problems))
        return self
