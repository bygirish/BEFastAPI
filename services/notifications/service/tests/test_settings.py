"""Rule X-11: development-only adapters and endpoints must refuse to start in production."""

import pytest
from pydantic import ValidationError

from notifications_service.domain.providers import PROVIDER_NAMES
from notifications_service.infrastructure.providers.registry import (
    _FACTORIES,
    build_chains,
    build_senders,
)
from notifications_service.settings import NotificationsSettings

SAFE = {"email_providers": "smtp", "sms_providers": "smtp", "digest_pepper": "a-real-secret"}


def test_provider_lists_accept_comma_separated_text() -> None:
    settings = NotificationsSettings(email_providers="smtp, console", sms_providers="console")
    assert settings.email_providers == ["smtp", "console"]


def test_unknown_providers_are_refused() -> None:
    with pytest.raises(ValidationError, match="unknown provider"):
        NotificationsSettings(email_providers="sendgrid")


@pytest.mark.parametrize(
    "overrides",
    [
        {"email_providers": "console"},
        {"sms_providers": "static"},
        {"email_providers": "memory"},
        {"dev_endpoints": True},
        {"digest_pepper": "dev-only-pepper-change-me"},
    ],
)
def test_dev_things_refuse_to_start_in_production(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="refusing to start in production"):
        NotificationsSettings(env="production", **{**SAFE, **overrides})  # type: ignore[arg-type]


def test_a_sane_production_config_starts() -> None:
    settings = NotificationsSettings(env="production", **SAFE)  # type: ignore[arg-type]
    assert settings.env == "production"


def test_dev_config_is_allowed_outside_production() -> None:
    for env in ("local", "test", "staging"):
        NotificationsSettings(env=env, email_providers="console", dev_endpoints=True)  # type: ignore[arg-type]


def test_registry_covers_exactly_the_declared_provider_names() -> None:
    assert _FACTORIES.keys() == PROVIDER_NAMES


def test_a_provider_must_support_the_channel_it_serves() -> None:
    settings = NotificationsSettings(sms_providers="smtp", email_providers="smtp")
    with pytest.raises(ValueError, match="cannot deliver sms"):
        build_chains(settings, build_senders(settings))
