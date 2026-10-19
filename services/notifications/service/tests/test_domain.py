"""Pure-domain tests: no database, no framework, no network."""

import pytest

from notifications_contracts import Channel
from notifications_service.domain.errors import (
    InvalidRecipient,
    TemplateVariablesMismatch,
    UnknownTemplate,
)
from notifications_service.domain.providers import DEV_ONLY_PROVIDERS, PROVIDER_NAMES
from notifications_service.domain.recipients import (
    mask_recipient,
    normalise_recipient,
    recipient_digest,
)
from notifications_service.domain.templates import TEMPLATES, render


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("+1 (415) 555-0123", "+14155550123"), (" +91-98765 43210 ", "+919876543210")],
)
def test_phone_numbers_are_normalised_to_e164(raw: str, expected: str) -> None:
    assert normalise_recipient(Channel.SMS, raw) == expected


@pytest.mark.parametrize("raw", ["9876543210", "+0123456789", "+12", "hello", "+1415555012345678"])
def test_bad_phone_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidRecipient):
        normalise_recipient(Channel.SMS, raw)


def test_emails_are_lowercased_and_validated() -> None:
    assert normalise_recipient(Channel.EMAIL, "  Asha@Example.COM ") == "asha@example.com"
    for bad in ["no-at-sign", "a@b", "a b@c.com", "@x.com"]:
        with pytest.raises(InvalidRecipient):
            normalise_recipient(Channel.EMAIL, bad)


def test_masking_hides_most_of_the_recipient() -> None:
    assert mask_recipient(Channel.EMAIL, "asha@example.com") == "a***@example.com"
    masked = mask_recipient(Channel.SMS, "+14155550123")
    assert masked == "+14*******23" and "5555" not in masked


def test_digest_is_keyed_stable_and_channel_scoped() -> None:
    a = recipient_digest(b"pepper-1", Channel.EMAIL, "asha@example.com")
    assert a == recipient_digest(b"pepper-1", Channel.EMAIL, "asha@example.com")
    assert a != recipient_digest(
        b"pepper-2", Channel.EMAIL, "asha@example.com"
    )  # without the pepper it can't be rebuilt
    assert a != recipient_digest(b"pepper-1", Channel.SMS, "asha@example.com")
    assert "asha" not in a


def test_templates_render_for_both_channels() -> None:
    email = render("otp", Channel.EMAIL, {"code": "111111", "ttl_minutes": "5"})
    assert email.subject == "Your verification code" and "111111" in email.body
    assert render("otp", Channel.SMS, {"code": "111111", "ttl_minutes": "5"}).subject is None
    assert render("welcome", Channel.EMAIL, {"name": "Asha"}).subject == "Welcome, Asha!"


def test_template_variables_must_match_exactly() -> None:
    with pytest.raises(UnknownTemplate):
        render("nope", Channel.SMS, {})
    with pytest.raises(TemplateVariablesMismatch) as missing:
        render("otp", Channel.SMS, {"code": "1"})
    assert missing.value.details["missing"] == ["ttl_minutes"]
    with pytest.raises(TemplateVariablesMismatch) as extra:
        render("password_changed", Channel.SMS, {"surprise": "x"})
    assert extra.value.details["unexpected"] == ["surprise"]
    with pytest.raises(TemplateVariablesMismatch):
        render("welcome", Channel.SMS, {"name": "x" * 500})


def test_variable_values_are_data_not_format_strings() -> None:
    message = render("welcome", Channel.SMS, {"name": "{0.__class__}"})
    assert "{0.__class__}" in message.body  # printed literally, never evaluated


def test_provider_name_sets_are_consistent() -> None:
    assert DEV_ONLY_PROVIDERS < PROVIDER_NAMES
    assert "smtp" not in DEV_ONLY_PROVIDERS
    assert {"otp", "welcome", "password_changed"} <= TEMPLATES.keys()
